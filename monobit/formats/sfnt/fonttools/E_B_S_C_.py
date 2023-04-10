from fontTools.misc import sstruct
from fontTools.ttLib.tables.E_B_L_C_ import (
    sbitLineMetricsFormat, SbitLineMetrics, DefaultTable,
    bytesjoin, safeEval, Strike
)

import logging


log = logging.getLogger(__name__)

ebscHeaderFormat = """
	> # big endian
	version:  16.16F
	numSizes: I
"""

# hori
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
        self.numSizes = len(self.bitmapScaleTables)
        dataList.append(sstruct.pack(ebscHeaderFormat, self))

        # dataSize = len(dataList[0])
        #
        # for _ in self.bitmapScaleTables:
        #     dataSize += len(("hori", "vert")) * sstruct.calcsize(sbitLineMetricsFormat)
        #     dataSize += sstruct.calcsize(bitmapScaleTableFormatPart2)

        for curTable in self.bitmapScaleTables:
            for metric in ("hori", "vert"):
                metricObj = vars(curTable)[metric]
                data = sstruct.pack(sbitLineMetricsFormat, metricObj)
                dataList.append(data)
            data = sstruct.pack(bitmapScaleTableFormatPart2, curTable)
            dataList.append(data)

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

    def __init__(self, **kwargs):
        vars(self).update(kwargs)

    # Returns all the simple metric names that bitmap size table
    # cares about in terms of XML creation.
    def _getXMLMetricNames(self):
        dataNames = sstruct.getformat(bitmapScaleTableFormatPart2)[1]
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
