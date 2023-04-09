from fontTools.misc import sstruct
from fontTools.ttLib.tables.E_B_L_C_ import (
    sbitLineMetricsFormat, SbitLineMetrics, DefaultTable
)

import logging


log = logging.getLogger(__name__)

ebscHeaderFormat = """
	> # big endian
	version:  16.16F
	numSizes: I
"""

#  hori
# vert
bitmapScaleTableFormatPart2 = """
	> # big endian
	ppemX:           B
	ppemY:           B
	substitutePpemX: B
	substitutePpemY: B
"""


class table_E_B_S_C_(DefaultTable.DefaultTable):

    def decompile(self, data, ttFont):

        # # Save the original data because offsets are from the start of the table.
        # origData = data
        i = 0

        dummy = sstruct.unpack(ebscHeaderFormat, data[:8], self)
        i += 8

        self.bitmapScaleTables = []
        for curStrikeIndex in range(self.numSizes):
            curTable = BitmapScaleTable()
            self.bitmapScaleTables.append(curTable)
            for metric in ("hori", "vert"):
                metricObj = SbitLineMetrics()
                vars(curTable)[metric] = metricObj
                dummy = sstruct.unpack2(
                    sbitLineMetricsFormat, data[i : i + 12], metricObj
                )
                i += 12
            dummy = sstruct.unpack(
                bitmapScaleTableFormatPart2, data[i : i + 4], curTable
            )
            i += 4


    def compile(self, ttFont):

        dataList = []
        self.numSizes = len(self.strikes)
        dataList.append(sstruct.pack(eblcHeaderFormat, self))

        # Data size of the header + bitmapSizeTable needs to be calculated
        # in order to form offsets. This value will hold the size of the data
        # in dataList after all the data is consolidated in dataList.
        dataSize = len(dataList[0])

        # The table will be structured in the following order:
        # (0) header
        # (1) Each bitmapSizeTable [1 ... self.numSizes]
        # (2) Alternate between indexSubTableArray and indexSubTable
        #     for each bitmapSizeTable present.
        #
        # The issue is maintaining the proper offsets when table information
        # gets moved around. All offsets and size information must be recalculated
        # when building the table to allow editing within ttLib and also allow easy
        # import/export to and from XML. All of this offset information is lost
        # when exporting to XML so everything must be calculated fresh so importing
        # from XML will work cleanly. Only byte offset and size information is
        # calculated fresh. Count information like numberOfIndexSubTables is
        # checked through assertions. If the information in this table was not
        # touched or was changed properly then these types of values should match.
        #
        # The table will be rebuilt the following way:
        # (0) Precompute the size of all the bitmapSizeTables. This is needed to
        #     compute the offsets properly.
        # (1) For each bitmapSizeTable compute the indexSubTable and
        #    	indexSubTableArray pair. The indexSubTable must be computed first
        #     so that the offset information in indexSubTableArray can be
        #     calculated. Update the data size after each pairing.
        # (2) Build each bitmapSizeTable.
        # (3) Consolidate all the data into the main dataList in the correct order.

        for _ in self.strikes:
            dataSize += sstruct.calcsize(bitmapSizeTableFormatPart1)
            dataSize += len(("hori", "vert")) * sstruct.calcsize(sbitLineMetricsFormat)
            dataSize += sstruct.calcsize(bitmapSizeTableFormatPart2)

        indexSubTablePairDataList = []
        for curStrike in self.strikes:
            curTable = curStrike.bitmapSizeTable
            curTable.numberOfIndexSubTables = len(curStrike.indexSubTables)
            curTable.indexSubTableArrayOffset = dataSize

            # Precompute the size of the indexSubTableArray. This information
            # is important for correctly calculating the new value for
            # additionalOffsetToIndexSubtable.
            sizeOfSubTableArray = (
                curTable.numberOfIndexSubTables * indexSubTableArraySize
            )
            lowerBound = dataSize
            dataSize += sizeOfSubTableArray
            upperBound = dataSize

            indexSubTableDataList = []
            for indexSubTable in curStrike.indexSubTables:
                indexSubTable.additionalOffsetToIndexSubtable = (
                    dataSize - curTable.indexSubTableArrayOffset
                )
                glyphIds = list(map(ttFont.getGlyphID, indexSubTable.names))
                indexSubTable.firstGlyphIndex = min(glyphIds)
                indexSubTable.lastGlyphIndex = max(glyphIds)
                data = indexSubTable.compile(ttFont)
                indexSubTableDataList.append(data)
                dataSize += len(data)
            curTable.startGlyphIndex = min(
                ist.firstGlyphIndex for ist in curStrike.indexSubTables
            )
            curTable.endGlyphIndex = max(
                ist.lastGlyphIndex for ist in curStrike.indexSubTables
            )

            for i in curStrike.indexSubTables:
                data = struct.pack(
                    indexSubHeaderFormat,
                    i.firstGlyphIndex,
                    i.lastGlyphIndex,
                    i.additionalOffsetToIndexSubtable,
                )
                indexSubTablePairDataList.append(data)
            indexSubTablePairDataList.extend(indexSubTableDataList)
            curTable.indexTablesSize = dataSize - curTable.indexSubTableArrayOffset

        for curStrike in self.strikes:
            curTable = curStrike.bitmapSizeTable
            data = sstruct.pack(bitmapSizeTableFormatPart1, curTable)
            dataList.append(data)
            for metric in ("hori", "vert"):
                metricObj = vars(curTable)[metric]
                data = sstruct.pack(sbitLineMetricsFormat, metricObj)
                dataList.append(data)
            data = sstruct.pack(bitmapSizeTableFormatPart2, curTable)
            dataList.append(data)
        dataList.extend(indexSubTablePairDataList)

        return bytesjoin(dataList)

    def toXML(self, writer, ttFont):
        writer.simpletag("header", [("version", self.version)])
        writer.newline()
        for curIndex, curStrike in enumerate(self.strikes):
            curStrike.toXML(curIndex, writer, ttFont)

    def fromXML(self, name, attrs, content, ttFont):
        if name == "header":
            self.version = safeEval(attrs["version"])
        elif name == "strike":
            if not hasattr(self, "strikes"):
                self.strikes = []
            strikeIndex = safeEval(attrs["index"])
            curStrike = Strike()
            curStrike.fromXML(name, attrs, content, ttFont, self)

            # Grow the strike array to the appropriate size. The XML format
            # allows for the strike index value to be out of order.
            if strikeIndex >= len(self.strikes):
                self.strikes += [None] * (strikeIndex + 1 - len(self.strikes))
            assert self.strikes[strikeIndex] is None, "Duplicate strike EBLC indices."
            self.strikes[strikeIndex] = curStrike


class BitmapScaleTable(object):

    # Returns all the simple metric names that bitmap size table
    # cares about in terms of XML creation.
    def _getXMLMetricNames(self):
        dataNames = sstruct.getformat(bitmapSizeTableFormatPart2)[1]
        return dataNames

    def toXML(self, writer, ttFont):
        writer.begintag("bitmapScaleTable")
        writer.newline()
        for metric in ("hori", "vert"):
            getattr(self, metric).toXML(metric, writer, ttFont)
        for metricName in self._getXMLMetricNames():
            writer.simpletag(metricName, value=getattr(self, metricName))
            writer.newline()
        writer.endtag("bitmapScaleTable")
        writer.newline()

    def fromXML(self, name, attrs, content, ttFont):
        # Create a lookup for all the simple names that make sense to
        # bitmap size table. Only read the information from these names.
        dataNames = set(self._getXMLMetricNames())
        for element in content:
            if not isinstance(element, tuple):
                continue
            name, attrs, content = element
            if name == "sbitLineMetrics":
                direction = attrs["direction"]
                assert direction in (
                    "hori",
                    "vert",
                ), "SbitLineMetrics direction specified invalid."
                metricObj = SbitLineMetrics()
                metricObj.fromXML(name, attrs, content, ttFont)
                vars(self)[direction] = metricObj
            elif name in dataNames:
                vars(self)[name] = safeEval(attrs["value"])
            else:
                log.warning("unknown name '%s' being ignored in BitmapScaleTable.", name)
