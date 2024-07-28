"""
monobit.storage.formats.geos - C64 GEOS font files

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from datetime import datetime
from itertools import count, accumulate

from monobit.storage import loaders, savers, Stream, Magic, FileFormatError
from monobit.core import Font, Glyph, Raster
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv, align

from monobit.storage.utils.limitations import ensure_single, make_contiguous


###############################################################################
# Font record in GEOS VLIR file
# https://www.lyonlabs.org/commodore/onrequest/geos/geos-fonts.html

_HEADER = le.Struct(
    baseline='uint8',
    stride='uint16',
    height='uint8',
    index_offset='uint16',
    bitstream_offset='uint16',
)

# characters 0x20 - 0x7f
# however, for sample files, the value there doesn't apper to be a valid offset
# nor is there a coherent image in the strike past offset[95]
_OFFSETS = le.uint16.array(97)


@loaders.register(
    name='vlir',
)
def load_geos_vlir_record(instream, *, extract_del:bool=False):
    """
    Load a bare GEOS font VLIR.

    extract_del: extract the unused DEL glyph 0x7f (defauult: False)
    """
    header = _HEADER.read_from(instream)
    logging.debug('header: %s', header)
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
    # drop glyph 0x7f (DEL) as it's never used and often garbage
    if not extract_del:
        glyphs = glyphs[:-1]
    props = dict(
        descent=header.height-header.baseline-1,
        ascent=header.baseline+1,
        encoding='ascii',
    )
    return Font(glyphs, **props).label()


@savers.register(linked=load_geos_vlir_record)
def save_geos_vlir_record(fonts, outstream):
    """Save font to a bare GEOS font VLIR."""
    font = ensure_single(fonts)
    font = _prepare_font_for_geos_vlir_record(font)
    outstream.write(_create_geos_vlir_record(font))


def _prepare_font_for_geos_vlir_record(font):
    """Prepare a font to be stored in a geos VLIR record."""
    font = font.label(match_graphical=False, match_whitespace=False)
    font = font.subset(chars=(chr(_c) for _c in _GEOS_RANGE))
    font = font.label(
        codepoint_from='ascii', overwrite=True,
        match_graphical=False, match_whitespace=False,
    )
    font = make_contiguous(font, full_range=_GEOS_RANGE, missing='empty')
    font = font.equalise_horizontal()
    return font


def _create_geos_vlir_record(font):
    """Save font to a bare GEOS font VLIR record."""
    # generate strike
    offsets = (0, *accumulate(_g.width for _g in font.glyphs))
    stride = ceildiv(offsets[-1], 8)
    rasters = [_g.pixels for _g in font.glyphs]
    # glyphs have been equalised so we can refer to the first one
    height = rasters[0].height
    baseline = height + font.glyphs[0].shift_up - 1
    rasters.append(
        Raster.blank(width=stride*8 - offsets[-1], height=height)
    )
    strike = Raster.concatenate(*rasters)
    offset_table = _OFFSETS(*offsets)
    header = _HEADER(
        baseline=baseline,
        stride=stride,
        height=height,
        index_offset=_HEADER.size,
        bitstream_offset=_HEADER.size + _OFFSETS.size,
    )
    logging.debug('header: %s', header)
    return b''.join((
        bytes(header),
        bytes(offset_table),
        strike.as_bytes(),
    ))


###############################################################################
# GEOS VLIR file in CONVERT (CVT) container
# https://ist.uwaterloo.ca/~schepers/formats/GEOS.TXT
# https://ist.uwaterloo.ca/~schepers/formats/CVT.TXT

# the CVT contains a signature block, info block and record block, followed by
# one or more VLIRs (whose starting sectors are given by the record block)
# each such record is one sectore, i.e. 256 bytes.
# However in the CVT files the two initial bytes, a linked-list pointer,
# are left out.

# https://ist.uwaterloo.ca/~schepers/formats/D64.TXT
# > File Type
_C64_FILETYPES = {
    0x00: 'Scratched (deleted file entry)',
    0x80: 'DEL',
    0x81: 'SEQ',
    0x82: 'PRG',
    0x83: 'USR',
    0x84: 'REL',
}

# > GEOS file structure
_GEOS_STRUCTURES = {
    0x00: 'Sequential',
    0x01: 'VLIR file',
}
# > GEOS filetype
_GEOS_FILETYPES = {
    0x00: 'Non-GEOS (normal C64 file)',
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
    # >  0F-FF - Undefined
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


_SEQ_SIGNATURE = b'SEQ formatted GEOS file V1.0'
_PRG_SIGNATURE = b'PRG formatted GEOS file V1.0'


@loaders.register(
    name='geos',
    patterns=('*.cvt',),
    magic=(
        Magic.offset(30) + _SEQ_SIGNATURE,
        Magic.offset(30) + _PRG_SIGNATURE,
    ),
)
def load_geos(instream, merge_mega:bool=True, extract_del:bool=False):
    """
    Load fonts from a GEOS ConVerT container.

    extract_del: extract the unused DEL glyph 0x7f (defauult: False)
    merge_mega: merge to mega font, if detected (default: True)
    """
    dir_entry = _DIR_BLOCK.read_from(instream)
    logging.debug('directory entry: %s',  dir_entry)
    sig_block = _SIG_BLOCK.read_from(instream)
    logging.debug('signature: %s', sig_block)
    if sig_block.signature not in (_SEQ_SIGNATURE, _PRG_SIGNATURE):
        raise FileFormatError(
            'Not a GEOS font file: incorrect signature '
            f'{sig_block.signature.decode("latin-1")}'
        )
    info_block = _INFO_BLOCK.read_from(instream)
    logging.debug('info block: %s', info_block)
    record_block = _RECORD_BLOCK.read_from(instream)
    logging.debug(
        'record block: %s',
        list(x for x in record_block if not bytes(x) == b'\0\xff')
    )
    if dir_entry.geos_filetype != _GEOS_FONT_TYPE:
        raise FileFormatError(
            'Not a GEOS font file: incorrect filetype '
            f'{dir_entry.geos_filetype:02x}'
        )
    # properties which don't change within the family
    family = _str_from_geos(dir_entry.filename.rstrip(b'\xa0'))
    class_text = _str_from_geos(info_block.class_text)
    if class_text.startswith(family):
        name, _, revision = class_text.partition('V')
        if name.strip() == family:
            class_text = None
    else:
        revision = None
    props = dict(
        family=family,
        revision=revision,
        # display icon in comment
        comment=Raster.from_bytes(tuple(info_block.icon), width=24).as_text(),
        notice=_str_from_geos(info_block.description),
    )
    props['geos.class_text'] = class_text
    props['geos.timestamp'] = (
        f'{dir_entry.year+1900:04d}-{dir_entry.month:02d}-{dir_entry.day:02d} '
        f'{dir_entry.hour:02d}:{dir_entry.minute:02d}'
    )
    # create fonts
    fonts = {}
    for data_size, ghptsize in zip(
            info_block.O_GHSETLEN,
            info_block.O_GHPTSIZES
        ):
        if not ghptsize or not data_size:
            continue
        # ptsize is (font_id << 6) + point_size
        font_id, height = divmod(ghptsize, 1<<6)
        logging.debug('Loading font id %d index %d', font_id, height)
        anchor = instream.tell()
        try:
            font = load_geos_vlir_record(
                Stream(instream, mode='r'), extract_del=extract_del
            )
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
            font = font.modify(font_id=font_id, **props)
            fonts[height] = font
    if merge_mega and _is_mega(fonts):
        return _merge_mega(fonts)
    else:
        return tuple(fonts.values())


def _is_mega(fonts):
    """Check if extracted fonts represent one mega font."""
    # mega fonts: glyphs are divided over multiple strikes
    # undefined glyphs are given as 1-pixel-wide
    # GHPTSIZE differs between strikes but actual pixel-size is the same
    # sometimes the last (empty) strike has a different height
    id_sizes = set(
        (_f.font_id, _f.pixel_size)
        for _index, _f in fonts.items() if _index != 54
    )
    # if 7 strikes exist and 6 have the same id and pixel_size, assume mega font
    return len(id_sizes) == 1 and tuple(fonts.keys()) == tuple(range(48, 55))


def _merge_mega(fonts):
    """Merge fonts to mega font."""
    logging.info('Mega font detected, merging.')
    fonts = tuple(fonts.values())
    # last strike should contain only empty or blank glyphs
    last_empty = all(_g.is_blank() for _g in fonts[-1].glyphs)
    if not last_empty:
        logging.warning(
            'Last strike in mega font is not empty: glyphs will be discarded.'
        )
    # take glyph of maximum width from each strike
    selected = tuple(
        max(glyphs, key=lambda _g: _g.width)
        for glyphs in zip(*(_f.glyphs for _f in fonts))
    )
    if len(set(_g.height for _g in selected)) > 1:
        logging.warning('Mega font strikes differ in height')
    if len(set(_g.shift_up for _g in selected)) > 1:
        logging.warning('Mega font strikes differ in baseline')
    fonts = (fonts[0].modify(glyphs=selected),)
    return fonts


def _str_from_geos(text):
    """Convert string from GEOS format."""
    return text.decode('ascii', 'replace').replace('\r', '\n')


###############################################################################

@savers.register(linked=load_geos)
def save_geos(fonts, outstream, *, mega:bool=False):
    """
    Save fonts to a GEOS ConVerT container.

    mega: save in mega font format (single font only; default: False)
    """
    fonts = tuple(_prepare_font_for_geos_vlir_record(_f) for _f in fonts)
    if not mega:
        logging.debug('Creating GEOS regular font.')
        subfonts, common_props = _prepare_geos(fonts)
    else:
        logging.debug('Creating GEOS mega font.')
        subfonts, common_props = _split_mega(fonts)
    _write_geos(subfonts, outstream, **common_props)


def _write_geos(
        subfonts, outstream,
        family, revision, font_id,
        notice, class_text, timestamp
    ):
    """Write out prepared fonts to GEOS format."""
    records = {
        _index: _create_geos_vlir_record(_f)
        for _index, _f in subfonts.items()
    }
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
        year, month, day, hour, min, *_ = dt.timetuple()
    else:
        year, month, day, hour, min = 1900, 1, 1, 0, 0
    dir_block = _DIR_BLOCK(
        # C64 USR file (0x03), closed (0x80)
        filetype=0x83,
        # no idea if this is a legal value
        sector=0x100,
        filename=_str_to_geos(family).ljust(16, b'\xa0'),
        # sems to be always one less in the hi byte than 'sector' above
        info_sector=0,
        # VLIR structure (Sequential is 0x00)
        geos_structure=0x01,
        # > GEOS filetype
        geos_filetype=_GEOS_FONT_TYPE,
        year=year-1900,
        month=month,
        day=day,
        hour=hour,
        minute=min,
        # filesize='uint16',
    )
    sig_block = _SIG_BLOCK(
        # "SEQ" also happens, but "PRG" is more common (yet filetype is USR)
        signature=_PRG_SIGNATURE,
        # notes field is "usually $00"
    )
    # create the info block
    info_block = _INFO_BLOCK(
        id_bytes=b'\x03\x15\xBF',
        # > Icon bitmap (sprite format, 63 bytes)
        icon=(le.uint8 * 63)(*_make_icon()),
        filetype=dir_block.filetype,
        geos_filetype=dir_block.geos_filetype,
        geos_structure=dir_block.geos_structure,
        # 3 addresses based on sample file
        load_address=0,
        end_address=0xffff,
        start_address=0,
        class_text=_str_to_geos(class_text) or _make_classtext(family, revision),
        O_GHFONTID=font_id,
        # ptsize is (font_id << 6) + point_size
        O_GHPTSIZES=(le.uint16 * 15)(*((font_id << 6) + _r for _r in records)),
        # the size in bytes of the corresponding VLIR record when loaded
        O_GHSETLEN=(le.uint16 * 15)(*(len(_r) for _r in records.values())),
        description=(_str_to_geos(notice) or _make_description(subfonts.keys())),
    )
    # create the record block
    empty = _RECORD_ENTRY(sector_count=0, last_size=0xff,)
    entries = [empty] * 127
    # entry index corresponds with font's pixel size
    for pixel_size, rec in records.items():
        entries[pixel_size] = _RECORD_ENTRY(
            sector_count=ceildiv(len(rec)+1, 254),
            last_size=(len(rec)+1) % 254,
        )
    record_block = _RECORD_BLOCK(*entries)
    # info block + record block + data blocks
    dir_block.filesize = 2 + sum(_e.sector_count for _e in entries)
    # write out
    outstream.write(bytes(dir_block))
    outstream.write(bytes(sig_block))
    outstream.write(bytes(info_block))
    outstream.write(bytes(record_block))
    for rec in records.values():
        outstream.write(rec)
        outstream.write(bytes((254 - len(rec)) % 254))


def _prepare_geos(fonts):
    """Validate fonts for storing in GEOS convert format; extract metadata."""
    if len(set(_f.family for _f in fonts)) > 1:
        raise FileFormatError(
            'GEOS font file can only store fonts from one family.'
        )
    if len(set(_f.pixel_size for _f in fonts)) != len(fonts):
        raise FileFormatError(
            'GEOS font file can only store fonts with distinct pixel sizes.'
        )
    if len(fonts) > 15:
        raise FileFormatError(
            'GEOS font file can only store at most 15 pixel sizes.'
        )
    if max(_f.pixel_size for _f in fonts) > 63:
        raise FileFormatError(
            'GEOS font file can only store fonts of up to 63 pixels tall.'
        )
    common_props = _get_metadata(fonts[0])
    # sort in ascending order of pixel size
    fonts = tuple(sorted(fonts, key=lambda _f: _f.pixel_size))
    # index fonts by size
    subfonts = {_f.pixel_size: _f for _f in fonts}
    return subfonts, common_props


# https://www.lyonlabs.org/commodore/onrequest/geos/geos-fonts.html
# > 48: $20-$2f (blank to '/')
# > 49: $30-$3f ('0' to '?')
# > 50: $40-$4f ('@' to 'O')
# > 51: $50-$5f ('P' to '_')
# > 52: $60-$6f ('`' to 'o')
# > 53: $70-$7f ('p' to DEL)
_MEGA_SUBSETS = {
    48: range(0x20, 0x30),
    49: range(0x30, 0x40),
    50: range(0x40, 0x50),
    51: range(0x50, 0x60),
    52: range(0x60, 0x70),
    53: range(0x70, 0x80),
}

_GEOS_RANGE = range(0x20, 0x80)


def _split_mega(fonts):
    """Prepare font for storing in mega format."""
    font = ensure_single(fonts)
    common_props = _get_metadata(font)
    subfonts = {
        _index: font.subset(codepoints=_subrange)
        for _index, _subrange in _MEGA_SUBSETS.items()
    }
    # > the point sizes containing partial character sets contain proper
    # > bitstream indices for each character they contain, but an offset of
    # > one pixel for the characters that do not appear in that record.
    placeholder = Glyph.blank(width=1, height=font.glyphs[0].height, shift_up=font.glyphs[0].shift_up)
    subfonts = {
        _index: _subfont.resample(codepoints=_GEOS_RANGE, missing=placeholder)
        for _index, _subfont in subfonts.items()
    }
    # > There is also a 54-point record, which contains a complete bitstream
    # > index for every character (e.g. the indices for '0' to '?' are the same
    # > as those in record 49), but no bitstream data
    subfonts[54] = Font(Glyph(codepoint=_c) for _c in _GEOS_RANGE)
    return subfonts, common_props


def _get_metadata(font):
    """Get font family metadata."""
    family = font.family[:15]
    revision = font.revision
    try:
        font_id = int(font.font_id)
    except ValueError:
        font_id = 1023
    if 0 > font_id > 1023:
        font_id = 1023
    notice = font.notice[:95]
    return dict(
        family=family,
        revision=revision,
        font_id=font_id,
        notice=notice or '',
        class_text=font.get_property('geos.class_text') or '',
        timestamp=font.get_property('geos.timestamp'),
    )


def _str_to_geos(text):
    """Convert string to GEOS format."""
    return text.replace('\n', '\r').encode('ascii', 'replace')


def _make_description(sizes):
    """Create standard description string."""
    sizes = tuple(sizes)
    # actually pixels not points
    pointlist = ', '.join(str(_size) for _size in sizes[:-1])
    if pointlist:
        pointlist += ' and '
    pointlist += str(sizes[-1])
    description = f'Available in {pointlist} point.'
    return _str_to_geos(description)[:95]


def _make_classtext(family, revision):
    """Create standard class text."""
    # 20 bytes, with null terminator
    if revision != '0':
        revision = revision[:3]
        text = f'{family.ljust(11)} V{revision.ljust(3)}'
    else:
        text = f'{family}'
    return _str_to_geos(text)


_FONT_ICON = """\
@@@@@@@@@@@@@@@@@@@@@@@@
@......................@
@......................@
@......................@
@.@@@@@@@..............@
@..@@...@...........@..@
@..@@..............@@..@
@..@@..............@@..@
@..@@@@...........@@@@.@
@..@@...@@@..@@@@..@@..@
@..@@..@@.@@.@@.@@.@@..@
@..@@..@@.@@.@@.@@.@@..@
@..@@..@@.@@.@@.@@.@@..@
@.@@@@..@@@..@@.@@..@@.@
@......................@
@......................@
@......................@
@......................@
@......................@
@......................@
@@@@@@@@@@@@@@@@@@@@@@@@
"""

def _make_icon():
    """Create standard icon."""
    icon = Glyph.from_vector(_FONT_ICON, stride=25, width=24, _0='.', _1='@')
    return icon.as_bytes()
