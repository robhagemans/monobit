"""
monobit.formats.geos - C64 GEOS font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import count

from ..storage import loaders, savers
from ..streams import Stream
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..struct import little_endian as le
from ..binary import ceildiv, align
from ..magic import Magic


@loaders.register(
    name='geos',
    patterns=('*.cvt',),
    magic=(
        Magic.offset(34) + b'formatted GEOS file',
    ),
)
def load_geos(instream, merge_mega:bool=True):
    """Load fonts from a GEOS ConVerT container."""
    return _load_geos_cvt(instream, merge_mega)

@loaders.register(
    name='vlir',
)
def load_geos_vlir(instream, offset:int=0):
    """
    Load a bare GEOS font VLIR.

    offset: starting offset in bytes of the VLIR record in the file (default 0)
    """
    instream.seek(offset)
    return _load_geos_vlir(instream)


###############################################################################
# GEOS font VLIR
# https://www.lyonlabs.org/commodore/onrequest/geos/geos-fonts.html

_HEADER = le.Struct(
    baseline='uint8',
    stride='uint16',
    height='uint8',
    index_offset='uint16',
    bitstream_offset='uint16',
)

# characters 0x20 - 0x7f
# do we get plus one for the offset to the end?
_OFFSETS = le.uint16.array(96)


def _load_geos_vlir(instream):
    """Load a bare GEOS font VLIR."""
    header = _HEADER.read_from(instream)
    logging.debug(header)
    instream.seek(header.index_offset)
    offsets = _OFFSETS.read_from(instream)
    instream.seek(header.bitstream_offset)
    strikebytes = instream.read(header.height * header.stride)
    strikebytes = strikebytes.ljust(header.height * header.stride, b'\0')
    strike = Raster.from_bytes(
        strikebytes,
        header.stride * 8, header.height,
    )
    # clip out glyphs
    glyphs = tuple(
        Glyph(
            strike.crop(left=_offset, right=max(0, header.stride*8 - _next)),
            codepoint=_cp,
            shift_up=-(header.height-header.baseline-1)
        )
        for _offset, _next, _cp in zip(offsets, offsets[1:], count(0x20))
    )
    props = dict(
        descent=header.height-header.baseline-1,
        ascent=header.baseline+1,
    )
    return Font(glyphs, **props)


###############################################################################
# CVT container
# https://ist.uwaterloo.ca/~schepers/formats/GEOS.TXT
# https://ist.uwaterloo.ca/~schepers/formats/CVT.TXT

# the CVT contains a signature block, info block and record block, followed by
# one or more VLIRs (whose starting sectors are given by the record block)
# each such record is one sectore, i.e. 256 bytes.
# However in the CVT files the two initial bytes, a linked-list pointer,
# are left out.

# https://ist.uwaterloo.ca/~schepers/formats/D64.TXT
# > File Type
# > $00 - Scratched (deleted file entry)
# >  80 - DEL
# >  81 - SEQ
# >  82 - PRG
# >  83 - USR
# >  84 - REL
_C64_FILETYPES = {
    0x00: 'Scratched',
    0x80: 'DEL',
    0x81: 'SEQ',
    0x82: 'PRG',
    0x83: 'USR',
    0x84: 'REL',
}

# > GEOS file structure
# >   $00 - Sequential
# >    01 - VLIR file
_GEOS_STRUCTURES = {
    0x00: 'Sequential',
    0x01: 'VLIR',
}
# > GEOS filetype
# >    $00 - Non-GEOS (normal C64 file)
# >     01 - BASIC
# >     02 - Assembler
# >     03 - Data file
# >     04 - System File
# >     05 - Desk Accessory
# >     06 - Application
# >     07 - Application Data (user-created documents)
# >     08 - Font File
# >     09 - Printer Driver
# >     0A - Input Driver
# >     0B - Disk Driver (or Disk Device)
# >     0C - System Boot File
# >     0D - Temporary
# >     0E - Auto-Execute File
# >  0F-FF - Undefined
_GEOS_FILETYPES = {
    0x00: 'Non-GEOS',
    0x01: 'BASIC',
    0x02: 'Assembler',
    0x03: 'Data file',
    0x04: 'System File',
    0x05: 'Desk Accessory',
    0x06: 'Application',
    0x07: 'Application Data (user-created documents)',
    0x08: 'Font File',
    0x09: 'Printer Driver',
    0x0A: 'Input Driver',
    0x0B: 'Disk Driver (or Disk Device)',
    0x0C: 'System Boot File',
    0x0D: 'Temporary',
    0x0E: 'Auto-Execute File',
}

_GEOS_FONT_TYPE = 0x08

# 30 bytes 0x1e
# https://ist.uwaterloo.ca/~schepers/formats/GEOS.TXT
_DIR_BLOCK = le.Struct(
    # > C64 filetype (see the section on D64 for an explanation)
    # > REL files are not allowed.
    filetype='uint8',
    # > Starting track/sector (02/02 from above) of C64 file if GEOS
    # > filetype is $00. If GEOS filetype is non-zero,  track/sector
    # > of single-sector RECORD block
    sector='uint16',
    # > Filename (in ASCII, padded with $A0, case varies)
    filename='16s',
    # > Track/sector location of info block
    info_sector='uint16',
    # > GEOS file structure
    geos_structure='uint8',
    # > GEOS filetype
    geos_filetype='uint8',
    # > Year (1900 + value)
    year='uint8',
    # > Month (1-12, $01 to $0C)
    month='uint8',
    # > Day (1-31, $01 to $1F)
    day='uint8',
    # > Hour (0-23, $00 to $17) in military format
    hour='uint8',
    # > Minute (0-59, $00 to $3B)
    minute='uint8',
    # > Filesize, in sectors (low/high byte order)
    filesize='uint16',
)

# https://ist.uwaterloo.ca/~schepers/formats/CVT.TXT
_SIG_BLOCK = le.Struct(
    # 0x1e   30
    # b'PRG formatted GEOS file V1.0'
    # b'SEQ formatted GEOS file V1.0'
    signature='28s',
    # 0x3a   58
    notes=le.uint8.array(196),
    # 0xfe  254
)

# https://ist.uwaterloo.ca/~schepers/formats/GEOS.TXT
_INFO_BLOCK = le.Struct(
    # 0x02 / 0xfe - cvt leaves out the word-size pointer at the start
    #        so sectors are only 254 bytes long
    # > Information sector ID bytes (03 15 BF). The "03" is  likely
    # > the bitmap width, and the "15" is likely the bitmap height,
    # > but rare exceptions do exist to this!
    id_bytes='3s', # > 03 15 bf
    # 0x101
    # > Icon bitmap (sprite format, 63 bytes)
    icon=le.uint8.array(63),
    # 0x140
    # > C64 filetype (same as that from the directory entry)
    filetype='uint8',
    # > GEOS filetype (same as that from the directory entry)
    geos_filetype='uint8',
    # > GEOS file structure (same as that from the dir entry)
    geos_structure='uint8',
    # 0x143
    # > Program load address
    load_address='uint16',
    # > Program end address (only with accessories)
    end_address='uint16',
    # > Program start address
    start_address='uint16',
    # 0x149
    # > Class text (terminated with a $00)
    class_text='20s',

    # 0x61 / 0x15d
    # > Author (with application data: name  of  application  disk,
    # > terminated with a $00. This string may not  necessarily  be
    # > set, or it may contain invalid data)
    #author='20s',
    # 0x75 / 0x171
    # > 75-88: If a document, the name of the application that created it.
    ##application='20s',
    # 0x89/0x185
    # > 89-9F: Available for applications, unreserved.
    #unreserved='23s',

    # here the font INFO section diverges from the standard one
    # https://www.lyonlabs.org/commodore/onrequest/geos/geos-fonts.html
    # 0x61 / 0x15d
    O_GHSETLEN=le.uint16.array(15),
    skip='uint8',
    # 0x80 / 0x17c
    O_GHFONTID='uint16',
    # 0x82 / 0x17e
    O_GHPTSIZES=le.uint16.array(15),
    # 0xa0 / 0x19c

    # > A0-FF: Description (terminated with a $00)
    description='96s',
)

# font_id values
# http://www.zimmers.net/geos/docs/fontfile.txt
# 0    BSW            13   Tilden
# 1    University     14   Evans
# 2    California     15   Durant
# 3    Roma           16   Telegraph
# 4    Dwinelle       17   Superb
# 5    Cory           18   Bowditch
# 6    Tolman         19   Ormond
# 7    Bubble         20   Elmwood
# 8    Fontknox       21   Hearst
# 9    Harmon         21   Brennens (BUG)
# 10   Mykonos        23   Channing
# 11   Boalt          24   Putnam
# 12   Stadium        25   LeConte


# >   If the file is a VLIR, then the RECORD block is of interest. This  single
# > sector is made up of up to 127 track/sector pointers, each of  which  point
# > to program sections (called RECORDS). VLIR files are comprised of  loadable
# > RECORDS (overlays, if you wish to use PC terminology). The first RECORD  is
# > what is always loaded first when you run that application. After that,  the
# > OS loads whatever RECORD it needs.
# >   When a T/S link of $00/$00 is encountered, we  are  at  the  end  of  the
# > RECORD block. If the T/S  link  is  a  $00/$FF,  then  the  record  is  not
# > available.

# https://ist.uwaterloo.ca/~schepers/formats/CVT.TXT
# >   Note that the RECORD block is modified  from  the  original  GEOS  entry.
# > Instead of containing the track and sector  references,  we  now  have  the
# > sector count and the size of the last sector in the chain
_RECORD_ENTRY = le.Struct(
    sector_count='uint8',
    last_size='uint8',
)
_RECORD_BLOCK = _RECORD_ENTRY.array(127)


def _load_geos_cvt(instream, merge_mega):
    """Load a GEOS ConVerT container."""
    dir_entry = _DIR_BLOCK.read_from(instream)
    sig_block = _SIG_BLOCK.read_from(instream)
    logging.debug(
        'filetype: %s',
        _C64_FILETYPES.get(dir_entry.filetype, dir_entry.filetype)
    )
    logging.debug(
        'GEOS structure: %s',
        _GEOS_STRUCTURES.get(dir_entry.geos_structure, dir_entry.geos_structure)
    )
    logging.debug(
        'GEOS filetype: %s',
        _GEOS_FILETYPES.get(dir_entry.geos_filetype, dir_entry.geos_filetype)
    )
    logging.debug(
        'timestamp: %02d-%02d-%02d %02d:%02d',
        dir_entry.year, dir_entry.month, dir_entry.day,
        dir_entry.hour, dir_entry.minute
    )
    logging.debug('signature: %s', bytes(sig_block.signature).decode('ascii', 'replace'))
    info_block = _INFO_BLOCK.read_from(instream)
    logging.debug('class: %s', info_block.class_text.decode('ascii', 'replace'))
    icon = Raster.from_bytes(tuple(info_block.icon), width=24)
    record_block = _RECORD_BLOCK.read_from(instream)
    logging.debug(info_block)
    logging.debug(list(x for x in record_block if not bytes(x) == b'\0\xff'))
    if dir_entry.geos_filetype != _GEOS_FONT_TYPE:
        logging.warning(
            'Not a GEOS font file: incorrect filetype %x.',
            dir_entry.geos_filetype
        )
    comment = '\n\n'.join((
        info_block.description.decode('ascii', 'replace').replace('\r', '\n'),
        icon.as_text(),
    ))
    fonts = []
    for data_size, ghptsize in zip(
            info_block.O_GHSETLEN,
            info_block.O_GHPTSIZES
        ):
        if not ghptsize or not data_size:
            continue
        # ptsize is (font_id << 6) + point_size
        font_id, height = divmod(ghptsize, 1<<6)
        logging.debug('Loading font id %d height %d', font_id, height)
        anchor = instream.tell()
        try:
            font = _load_geos_vlir(Stream(instream, mode='r'))
        except ValueError as e:
            logging.warning(
                'Could not load font id %d size %d: %s', font_id, height, e
            )
            # flag to skip to next sector
            font = None
        true_data_size = instream.tell() - anchor
        if true_data_size != data_size:
            logging.warning(
                'Actual size 0x%x differs from reported size 0x%x',
                true_data_size, data_size
            )
        # go to end of sector
        # 254 bytes per sector - the cvt does not store the initial pointer
        nxt = ceildiv(true_data_size, 254) * 254
        instream.seek(anchor + nxt)
        if font is not None:
            font = font.modify(
                family=dir_entry.filename.rstrip(b'\xa0').decode('ascii', 'replace'),
                comment=comment,
                font_id=font_id,
            )
            fonts.append(font)
    # mega fonts: glyphs are divided over multiple strikes
    # undefined glyphs are given as 1-pixel-wide
    # last strike contains only empty or blank glyphs
    last_empty = all(_g.is_blank() for _g in fonts[-1].glyphs)
    # GHPTSIZE differs between strikes but actual pixel-size is the same
    # sometimes the last (empty) strike has a different height
    id_sizes = set((_f.font_id, _f.pixel_size) for _f in fonts[:-1])
    # if all strikes have the same id and pixel_size, assume this is a mega font
    if merge_mega and len(id_sizes) == 1 and last_empty:
        logging.info('Mega font detected, merging.')
        # take glyph of maximum width from each strike
        selected = (
            max(glyphs, key=lambda _g: _g.width)
            for glyphs in zip(*(_f.glyphs for _f in fonts))
        )
        fonts = (fonts[0].modify(glyphs=selected),)
    return fonts
