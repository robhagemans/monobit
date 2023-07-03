"""
monobit.formats.palm - Palm OS databases and font resources

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..struct import big_endian as be
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..magic import FileFormatError, Magic

from .mac.nfnt import extract_nfnt, convert_nfnt


# offset magic: b'FontFont' at offset 0x3c (type, creator fields)
@loaders.register(
    name='palm',
    magic=(Magic.offset(0x3c) + b'FontFont',),
    patterns=('*.pdb',),
)
def load_palm(instream):
    """Load fonts from a Palm OS PDB file."""
    palm_data = _read_palm(instream)
    fonts = _convert_palm(palm_data)
    return fonts

@loaders.register(
    name='palm-prc',
    patterns=('*.prc',),
)
def load_palm_prc(instream):
    """Load fonts from a Palm OS PRC file."""
    palm_data = _read_palm_prc(instream)
    fonts = _convert_palm(palm_data)
    return fonts


##############################################################################
# PDB / PRC database
# https://web.archive.org/web/20050212083234/http://www.palmos.com/dev/support/docs/fileformats/Intro.html
# https://web.archive.org/web/20050212082335/http://www.palmos.com/dev/support/docs/fileformats/PDB+PRCFormat.html#972428

_PDB_HEADER = be.Struct(
    # A 32-byte long, null-terminated string containing the name of the database
    # on the Palm Powered handheld. The name is restricted to 31 bytes in
    # length, plus the terminator byte.
    name='32s',
    # The attribute flags for the database. For PQA databases, this field always
    # has the value dmHdrAttrBackup | dmHdrAttrLaunchableData
    attributes='uint16',
    # The application-specific version of the database layout.
    version='uint16',
    # The creation date of the database, specified as the number of seconds
    # since 12:00 A.M. on January 1, 1904.
    creationDate='uint32',
    # The date of the most recent modification of the database, specified as the
    # number of seconds since 12:00 A.M. on January 1, 1904.
    modificationDate='uint32',
    # The date of the most recent backup of the database, specified as the
    # number of seconds since 12:00 A.M. on January 1, 1904.
    lastBackupDate='uint32',
    # The modification number of the database.
    modificationNumber='uint32',
    # The local offset from the beginning of the database header data to the
    # start of the optional, application-specific appInfo block.
    # This value is set to NULL for databases that do not include an appInfo block.
    appInfoID='uint32',
    # The local offset from the beginning of the PDB header data to the start of
    # the optional, application-specific sortInfo block.  This value is set to
    # NULL for databases that do not include an sortInfo block type
    sortInfoID='uint32',
    # The database type identifier.
    # For PDB databases, the value of this field depends on the creator application.
    # For PRC databases, this field usually has the value 'appl'.
    # For PQA databases, this field always has the value 'pqa'.
    type='4s',
    # The database creator identifier.
    # For PQA databases, this feld always has the value 'clpr'.
    creator='4s',
    # Used internally by the Palm OS to generate unique identifiers for records
    # on the Palm device when the database is loaded into the device.
    # For PRC databases, this value is normally not used and is set to 0.
    # For PQA databases, this value is not used, and is set to 0.
    uniqueIDSeed='uint32',
    # A list of the records or resources in the database, as described in the
    # next section.
    # IMPORTANT: There is always a gap between the final record list in the
    # header and the first block of data in the database, where the first block
    # might be one of the following: the appInfo block, the sortInfo block, raw
    # record or resource data, or the end of the file. The gap is traditionally
    # two bytes long; however, if you write code to parse a database, your code
    # should be able to handle any size gap, from zero bytes long and up.
    #recordList
)

_RECORD_LIST = be.Struct(
    # The local chunk ID of the next record list in this database. This is 0 if
    # there is no next record list, which is almost always the case.
    nextRecordListID='uint32',
    # The number of record entries in this list.
    numRecords='uint16',
    # The start of an array of record entry structures, each of which represents
    # a single record in the list.
    #firstEntry
)

_PDB_ENTRY = be.Struct(
    # The local offset from the top of the PDB to the start of the raw record
    # data for this entry.  Note that you can determine the size of each chunk
    # of raw record data by subtracting the starting offset of the chunk from
    # the starting offset of the following chunk. If the chunk is the last
    # chunk, it's end is determined by the end of the file.
    localChunkID='uint32',
    # Attributes of the record.
    attributes='uint8',
    # A three-byte long unique ID for the record.
    uniqueID=be.uint8 * 3,
)

_PRC_ENTRY = be.Struct(
    # The resource type.
    type='4s',
    # The ID of the resource.
    id='uint16',
    # The local offset from the top of the PRC to the start of the resource data
    # for this entry.  Note that you can determine the size of each chunk of raw
    # resource data by subtracting the starting offset of the chunk from the
    # starting offset of the following chunk. If the chunk is the last chunk,
    # it's end is determined by the end of the file.
    localChunkID='uint32',
)

# we ignore the following, if they exist:
# AppInfo Block (optional)
# SortInfo Block (optional)


def _read_header(instream):
    """Read a PDB /PRC header."""
    header = _PDB_HEADER.read_from(instream)
    recordlist = _RECORD_LIST.read_from(instream)
    return Props(
        header=header,
        recordlist=recordlist,
    )

def _read_palm(instream):
    """Read a PDB file."""
    props = _read_header(instream)
    if (props.header.type, props.header.creator) != (b'Font', b'Font'):
        logging.warning(
            'Not a Font PDB: type `%s` creator `%s`',
            props.header.type, props.header.creator
        )
    entries = _PDB_ENTRY.array(props.recordlist.numRecords).read_from(instream)
    nfnts = []
    for entry in entries:
        instream.seek(entry.localChunkID)
        data = instream.read()
        # can be `NFNT` (0x9000) or `nfnt` (0x9200)
        # or `afnx` format (?)
        # currently we're just assuming NFNT
        try:
            nfnt = extract_nfnt(data, offset=0)
        except ValueError as e:
            logging.warning('Could not read record: %s', e)
            continue
        nfnts.append(nfnt)
    return props | Props(entries=tuple(entries), records=nfnts)


def _read_palm_prc(instream):
    """Read a PRC file."""
    props = _read_header(instream)
    entries = _PRC_ENTRY.array(props.recordlist.numRecords).read_from(instream)
    nfnts = []
    for entry in entries:
        logging.debug(
            'Found record of type `%s` id %d at offset 0x%X',
            entry.type.decode('latin-1'),
            entry.id,
            entry.localChunkID
        )
        if entry.type not in (b'NFNT', b'nfnt'):
            continue
        if entry.type == b'nfnt':
            logging.warning('Palm v2 (nfnt) format not implemented.')
        instream.seek(entry.localChunkID)
        data = instream.read()
        # currently we're just assuming NFNT
        try:
            nfnt = extract_nfnt(data, offset=0)
        except ValueError as e:
            logging.warning('Could not read record: %s', e)
            continue
        nfnts.append(nfnt)
    return props | Props(entries=tuple(entries), records=nfnts)


def _convert_palm(palm_data):
    """Convert a Palm OS font data structure to Font."""
    fonts = (
        convert_nfnt({}, **_nfnt)
        for _nfnt in palm_data.records
    )
    fonts = tuple(
        _font.modify(
            family=palm_data.header.name.decode('latin-1'),
            revision=palm_data.header.modificationNumber,
            source_format=f'[Palm] {_font.source_format}',
        ).label(char_from='palm-os')
        for _font in fonts
    )
    return fonts
