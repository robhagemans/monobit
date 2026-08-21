"""
monobit.storage.fontformats.apple.palm - Palm OS databases and NFNT font resources

(c) 2023--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be
from monobit.base import Props, UnsupportedError, FileFormatError
from monobit.storage import loaders, savers
from monobit.core import Font, Glyph
from monobit.storage import Magic

from .nfnt import extract_nfnt, convert_nfnt
from .nfnt2 import extract_nfnt2
from .grayfont import extract_grayfont, extract_gxyz


# offset magic: b'FontFont' at offset 0x3c (type, creator fields)
@loaders.register(
    name='palm',
    magic=(Magic.offset(0x3c) + b'FontFont',),
    patterns=('*.pdb',),
)
def load_palm(instream):
    """Load fonts from a Palm OS PDB file."""
    palm_data = _read_palm_pdb(instream)
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


def _read_palm_pdb(instream):
    """Read a PDB file."""
    header = _PDB_HEADER.read_from(instream)
    logging.debug('header: %s', header)
    if header.type != b'Font':
        logging.warning(
            'May not be a Font PDB: type `%s`, creator `%s`',
            header.type.decode('latin-1'), header.creator.decode('latin-1')
        )
    recordlist = _RECORD_LIST.read_from(instream)
    entries = _PDB_ENTRY.array(recordlist.numRecords).read_from(instream)
    logging.debug('PDB record list: %s', entries)
    resources = {}
    for entry in entries:
        instream.seek(entry.localChunkID)
        resources[entry.uniqueID] = _read_resource(instream, entry.uniqueID)
    return Props(
        header=header, recordlist=recordlist,
        entries=tuple(entries), records=resources,
    )


def _read_palm_prc(instream):
    """Read a PRC file."""
    header = _PDB_HEADER.read_from(instream)
    logging.debug('header: %s', header)
    recordlist = _RECORD_LIST.read_from(instream)
    entries = _PRC_ENTRY.array(recordlist.numRecords).read_from(instream)
    logging.debug('PRC record list: %s', entries)
    resources = {}
    for entry in entries:
        entry_type = entry.type.decode('latin-1')
        logging.debug(
            'Found record of type `%s` id %d at offset 0x%X',
            entry_type,
            entry.id,
            entry.localChunkID
        )
        instream.seek(entry.localChunkID)
        resources[entry.id] = _read_resource(instream, entry.id, entry_type)
    # TODO - we can't map records to entries, multiple records for nfnt
    return Props(
        header=header, recordlist=recordlist,
        entries=tuple(entries), records=resources,
    )


def _read_resource(instream, entry_id, entry_type=''):
    """Read a Palm font resource."""
    magic = instream.peek(2)[:2]
    entryprops = Props(id=entry_id, type=entry_type)
    description = f'id `{entry_id}` type `{entry_type}` magic {magic.hex()}'
    resource = Props(format='')
    try:
        # resource name is not dependable for Palm
        # - font resources may have ad-hoc names in some programs: 'FONT', 'tFnt'
        # - 'NFNT' and 'nfnt' named resources may be GrayFont headers
        if magic == b'\x90\0':
            logging.debug('Reading NFNT resource: %s', description)
            resource = Props(format='NFNT', data=extract_nfnt(instream))
        elif magic == b'\x92\0':
            logging.debug('Reading nfnt (v2) resource: %s', description)
            resource = Props(format='nfnt2', data=extract_nfnt2(instream, format='nfnt2'))
        elif magic == b'\0\x92' and entry_type == 'afnx': # also xFnt?
            logging.debug('Reading afnx resource: %s', description)
            resource = Props(format='nfnt2', data=extract_nfnt2(instream, format='afnx'))
        elif entry_type in ('GrFn', 'NFNT', 'nfnt'): # also GrFf?
            if magic in (b'\0\1', b'\0\2', b'\0\3', b'\0\4'):
                logging.debug('Reading big-endian GrayFont resource: %s', description)
                resource = Props(format='GrFn', data=extract_grayfont(instream, endian='big'))
            elif magic in (b'\1\0', b'\2\0', b'\3\0', b'\4\0'):
                logging.debug('Reading little-endian GrayFont resource: %s', description)
                resource = Props(format='GrFn', data=extract_grayfont(instream, endian='little'))
        elif entry_type[:2] in ('GU', 'GL', 'GR') and entry_type[2:] in ('14', '34'):
            logging.debug('Reading GrayFont bitmap resource: %s', description)
            resource = Props(format='GXYZ', data=extract_gxyz(instream))
        else:
            logging.debug('Skipping unknown resource: %s', description)
    except (ValueError, FileFormatError) as e:
        # negative array length throws valueerror, not enough data throws structerror <= fileformaterror
        logging.warning('Could not read resource: %s', e)
    return entryprops | resource


def _combine_resources(records):
    """Combine resources holding data for the same font."""
    fontdata = []
    for record in records.values():
        if record.format in ('NFNT', 'nfnt2'):
            fontdata.append(record)
        elif record.format == 'GrFn':
            combined_record = record
            combined_record.data.glyphs = []
            for cp, glyph_info in enumerate(record.data.glyph_info):
                bm_info = record.data.bitmaps_info[glyph_info.resourceNumber-1]
                combined_record.data.glyphs.append(
                    Glyph(
                        records[bm_info.resourceID].data[glyph_info.positionInResourceIndex],
                        codepoint=cp
                    )
                )
            fontdata.append(combined_record)
    return fontdata

def _convert_palm(palm_data):
    """Convert a Palm OS font data structure to Font."""
    fontdata = _combine_resources(palm_data.records)
    fonts = []
    for record in fontdata:
        if record.format == 'NFNT':
            fonts.append(convert_nfnt(**record.data))
        elif record.format == 'nfnt2':
            fonts.extend(convert_nfnt(**_data) for _data in record.data)
        elif record.format == 'GrFn':
            fonts.append(Font(record.data.glyphs, source_format='grayfont'))
    fonts = tuple(
        _font.modify(
            family=palm_data.header.name.decode('latin-1'),
            revision=palm_data.header.modificationNumber,
            source_format=f'[Palm] {_font.source_format}',
        ).label(char_from='palm-os')
        for _font in fonts
    )
    return fonts
