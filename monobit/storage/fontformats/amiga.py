"""
monobit.storage.fontformats.amiga - Amiga font format

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
from pathlib import Path
from itertools import accumulate

from monobit.storage import loaders, savers, Regex
from monobit.core import Font, Glyph, Raster
from monobit.base.struct import flag, bitfield, big_endian as be
from monobit.base.binary import ceildiv
from monobit.base import Props, Coord, FileFormatError, UnsupportedError
from monobit.storage.utils.limitations import ensure_single, make_contiguous


###################################################################################################
# AmigaOS font format
#
# developer docs: Graphics Library and Text
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text
# http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03D2.html
#
# references on binary file format
# http://amiga-dev.wikidot.com/file-format:hunk
# https://archive.org/details/AmigaDOS_Technical_Reference_Manual_1985_Commodore/page/n13/mode/2up (p.14)


# latin-1 seems to be the standard for amiga strings,
# see e.g. https://wiki.amigaos.net/wiki/FTXT_IFF_Formatted_Text#Data_Chunk_CHRS
_ENCODING = 'latin-1'

# amiga header constants
_MAXFONTPATH = 256
_MAXFONTNAME = 32

# file ids
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text#The_Composition_of_a_Bitmap_Font_on_Disk
_FCH_ID = 0x0f00
_TFCH_ID = 0x0f02
_NONBITMAP_ID = 0x0f03
# disk font header
_DFH_ID = 0x0f80

# hunk ids
# http://amiga-dev.wikidot.com/file-format:hunk
_HUNK_HEADER = 0x3f3
_HUNK_CODE = 0x3e9
_HUNK_DATA = 0x3ea
_HUNK_RELOC32 = 0x3ec
_HUNK_END = 0x3f2

# tf_Flags values
_TF_FLAGS = be.Struct(
    # 0x80 the font has been removed
    FPF_REMOVED=flag,
    # 0x40 size explicitly designed, not constructed
    FPF_DESIGNED=flag,
    # 0x20 character sizes can vary from nominal
    FPF_PROPORTIONAL=flag,
    # 0x10 This font was designed for a Lores Interlaced screen (320x400 NTSC)
    FPF_WIDEDOT=flag,
    # 0x08 This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
    FPF_TALLDOT=flag,
    # 0x04 This font is designed to be printed from from right to left
    FPF_REVPATH=flag,
    # 0x02 font is from diskfont.library
    FPF_DISKFONT=flag,
    # 0x01 font is in rom
    FPF_ROMFONT=flag
)

# tf_Style values
_TF_STYLE = be.Struct(
    # 0x80 the TextAttr is really a TTextAttr
    FSF_TAGGED=flag,
    # 0x40 this uses ColorTextFont structure
    FSF_COLORFONT=flag,
    unused=bitfield('B', 2),
    # 0x08 extended face (wider than normal)
    FSF_EXTENDED=flag,
    # 0x04 italic (slanted 1:2 right)
    FSF_ITALIC=flag,
    # 0x02 bold face text (OR-ed w/ shifted)
    FSF_BOLD=flag,
    # 0x01 underlined (under baseline)
    FSF_UNDERLINED=flag,
)

# Amiga hunk file header
# http://amiga-dev.wikidot.com/file-format:hunk#toc6
#   hunk_id = uint32
#   null-null-terminated string table
_HUNK_FILE_HEADER_1 = be.Struct(
    table_size='uint32',
    first_hunk='uint32',
    last_hunk='uint32',
)
#   hunk_sizes = uint32 * (last_hunk-first_hunk+1)

# disk font header
_AMIGA_HEADER = be.Struct(
    # struct DiskFontHeader
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node05F9.html#line61
    dfh_NextSegment='I',
    # *here* is the reference point for addresses/pointers in the file
    dfh_ReturnCode='I',
    # struct Node
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    dfh_ln_Succ='I',
    dfh_ln_Pred='I',
    dfh_ln_Type='B',
    dfh_ln_Pri='b',
    dfh_ln_Name='I',
    dfh_FileID='H',
    dfh_Revision='H',
    dfh_Segment='i',
    dfh_Name=be.char * _MAXFONTNAME,
    # struct Message at start of struct TextFont
    # struct Message http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    tf_ln_Succ='I',
    tf_ln_Pred='I',
    tf_ln_Type='B',
    tf_ln_Pri='b',
    tf_ln_Name='I',
    tf_mn_ReplyPort='I',
    tf_mn_Length='H',
    # struct TextFont http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    tf_YSize='H',
    tf_Style=_TF_STYLE,
    tf_Flags=_TF_FLAGS,
    tf_XSize='H',
    tf_Baseline='H',
    tf_BoldSmear='H',
    tf_Accessors='H',
    tf_LoChar='B',
    tf_HiChar='B',
    tf_CharData='I',
    tf_Modulo='H',
    tf_CharLoc='I',
    tf_CharSpace='I',
    tf_CharKern='I',
)


# location table entry
_LOC_ENTRY = be.Struct(
    offset='uint16',
    width='uint16',
)


# struct FontContentsHeader
# .font directory file
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text#Composition_of_a_Bitmap_Font_on_Disk
_FONT_CONTENTS_HEADER = be.Struct(
    fch_FileID='uword',
    fch_NumEntries='uword',
    # followed by array of FontContents or TFontContents
)

# struct FontContents
_FONT_CONTENTS = be.Struct(
    fc_FileName=be.char * _MAXFONTPATH,
    fc_YSize='uword',
    fc_Style=_TF_STYLE,
    fc_Flags=_TF_FLAGS,
)

# struct TFontContents
# extra tags stored at the back of the tfc_FileName field
_T_FONT_CONTENTS = be.Struct(
    tfc_FileName=be.uint8 * (_MAXFONTPATH-2),
    tfc_TagCount='uword',
    tfc_YSize='uword',
    tfc_Style=_TF_STYLE,
    tfc_Flags=_TF_FLAGS,
)

# https://wiki.amigaos.net/wiki/Tags
_TAG_ITEM = be.Struct(
    # identifies the type of this item
    ti_Tag='uint32',
    # type-specific data, can be a pointer
    # ti_Data='uint32',
    ti_Data_hi = 'uint16',
    ti_Data_lo = 'uint16',
)

# http://amigadev.elowar.com/read/ADCD_2.1/Includes_and_Autodocs_2._guide/node00A8.html
#   #define	TA_DeviceDPI	(1|TAG_USER)
#   /* Tag value is Point union: */
#   /* Hi word XDPI, Lo word YDPI */
# http://amigadev.elowar.com/read/ADCD_2.1/Includes_and_Autodocs_2._guide/node012E.html#line18
#   #define TAG_USER  (1L<<31)    /* differentiates user tags from system tags*/
_TAG_DONE = 0
_TA_DEVICEDPI = (1 << 31) | 1

# https://d0.se/include/exec/nodes.h
# /*----- sNode Types for LN_TYPE -----*/
_NT_FONT = 12

# font name is 26 bytes from the start of the return code
_NAME_POINTER = 26

# http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node05BA.html
# MOVEQ     #-1,D0      ; Provide an easy exit in case this file is
# RTS                   ; "Run" instead of merely loaded.
_RETURN_CODE = 0x70ff4e75


###################################################################################################
# read Amiga font

@loaders.register(
    name='amiga-fc',
    magic=(b'\x0f\0', b'\x0f\2'),
    patterns=('*.font',),
)
def load_amiga_fc(instream):
    """Load fonts from Amiga disk font contents (.FONT) file."""
    fch = _FONT_CONTENTS_HEADER.read_from(instream)
    if fch.fch_FileID in (_FCH_ID, _TFCH_ID):
        pass
    elif fch.fch_FileID == _NONBITMAP_ID:
        raise UnsupportedError('IntelliFont Amiga outline fonts not supported.')
    else:
        raise FileFormatError(
            'Not an Amiga font contents file: '
            f'incorrect magic bytes 0x{fch.fch_FileID:04X} '
            f'not in (0x{_FCH_ID:04X}, 0x{_TFCH_ID:04X}).'
        )
    # TFontContents is a FontContents with re-interpreted fc_FileName field
    contentsarray = (_FONT_CONTENTS*fch.fch_NumEntries).read_from(instream)
    pack = []
    for fc in contentsarray:
        dpi = None
        if fch.fch_FileID == _TFCH_ID:
            logging.debug('Amiga font contents using TFontContents structure')
            tfc = _T_FONT_CONTENTS.from_bytes(bytes(fc))
            # *  if tfc_TagCount is non-zero, tfc_FileName is overlaid with
            # *  Text Tags starting at:  (struct TagItem *)
            # *      &tfc_FileName[MAXFONTPATH-(tfc_TagCount*sizeof
            # *                                 (struct TagItem))]
            # Note that this means the last (TAG_DONE) tag is truncated
            # by 2 bytes, because the fileName field is MAXFONTPATH-2 long
            # omit this last tag:
            tags = (_TAG_ITEM * (tfc.tfc_TagCount - 1)).from_bytes(bytes(
                tfc.tfc_FileName[_MAXFONTPATH-tfc.tfc_TagCount*_TAG_ITEM.size:]
            ))
            # only known/documented use for tags is to store dpi values for aspect ratio
            for tag in tags:
                if tag.ti_Tag == _TA_DEVICEDPI:
                    dpi = (tag.ti_Data_hi, tag.ti_Data_lo)
                else:
                    logging.debug('Ignoring unrecognised tag: %s', tag)
        # we'll get ysize, style and flags from the file itself, we just need a path.
        name = fc.fc_FileName.decode(_ENCODING)
        # note case insensitive match on open (amiga os is case-insensitive)
        try:
            with instream.where.open(name, 'r') as stream:
                font = load_amiga(stream)
                font = font.modify(dpi=dpi)
                pack.append(font)
        except EnvironmentError as exc:
            logging.error("Could not open Amiga font file '%s': %s", name, exc)
    return pack


@loaders.register(
    name='amiga',
    magic=(b'\0\0\x03\xf3',),
    # digits-only filename
    patterns=(Regex(r'\d+'),),
)
def load_amiga(instream):
    """Load font from Amiga disk font file."""
    # read & ignore header
    hfh1, hunk_size = _read_header(instream)
    logging.debug('header: %s', hfh1)
    logging.debug('size: %s', hunk_size)
    amiga_props, glyphs = _read_font_hunk(instream)
    logging.info('Amiga properties:')
    for name, value in vars(amiga_props).items():
        logging.info('    %s: %s', name, value)
    props, glyphs = _convert_amiga_font(amiga_props, glyphs)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    font = Font(glyphs, **vars(props))
    # fill out character labels based on latin-1 encoding
    font = font.label()
    return font


def _read_header(f):
    """Read file header."""
    # read header id
    hunk_id = int(be.uint32.read_from(f))
    if hunk_id != _HUNK_HEADER:
        raise FileFormatError(
            'Not an Amiga font data file: '
            f'magic constant 0x{hunk_id:03X} != 0x{_HUNK_HEADER:03X}'
        )
    # a unk file can have a list of n null-erminated library names here
    # but this is not legal for font files
    num_library_names = int(be.uint32.read_from(f))
    if num_library_names:
        raise FileFormatError(
            'Not an Amiga font data file: non-empty library names section.'
        )
    header = _HUNK_FILE_HEADER_1.read_from(f)
    if header.last_hunk or header.first_hunk:
        raise FileFormatError(
            'Not an Amiga font data file: more than one hunk.'
        )
    # list of memory sizes of hunks in this file (in number of ULONGs)
    # this seems to exclude overhead, so not useful to determine disk sizes
    hunk_size = int(be.uint32.read_from(f))
    return header, hunk_size


def _read_font_hunk(f):
    """Parse the font data blob."""
    hunk_id = int(be.uint32.read_from(f))
    # *should* be a code hunk, but data hunk fonts have ben seen in the wild
    if hunk_id not in (_HUNK_CODE, _HUNK_DATA):
        raise FileFormatError(
            f'Not an Amiga font data file: hunk id 0x{hunk_id:03X}.'
        )
    # location reference point loc = f.tell() + 4
    amiga_props = _AMIGA_HEADER.read_from(f)
    # these seem to be consistently set
    if (
            amiga_props.dfh_FileID != _DFH_ID
            or amiga_props.tf_ln_Type != _NT_FONT
            or amiga_props.tf_ln_Name != 0x1a
        ):
        raise FileFormatError(
            'Not an Amiga font data file: incorrect type fields.'
        )
    # remainder is the font strike
    glyphs = _read_strike(f, amiga_props)
    return amiga_props, glyphs


def _read_strike(f, props):
    """Read and interpret the font strike and related tables."""
    # remainder is the font strike
    data = f.read()
    # the reference point for offsets in the hunk is just before the ReturnCode
    loc = - _AMIGA_HEADER.size + 4
    # location data
    # one additional for default glyph
    nchars = (props.tf_HiChar - props.tf_LoChar + 1) + 1
    locs = _LOC_ENTRY.array(nchars).from_bytes(data, loc + props.tf_CharLoc)
    # spacing table
    # spacing can be negative
    if props.tf_Flags.FPF_PROPORTIONAL and props.tf_CharSpace:
        spacing = be.int16.array(nchars).from_bytes(data, loc + props.tf_CharSpace)
    else:
        spacing = [props.tf_XSize] * nchars
    # kerning table
    # amiga "kerning" is a left bearing; can be pos (to right) or neg
    if props.tf_CharKern:
        kerning = be.int16.array(nchars).from_bytes(data, loc + props.tf_CharKern)
    else:
        kerning = [0] * nchars
    # bitmap strike
    strike = Raster.from_bytes(
        data[
            loc + props.tf_CharData
            : loc + props.tf_CharData + props.tf_Modulo*props.tf_YSize
        ],
        height=props.tf_YSize,
    )
    # extract glyphs
    pixels = (
        strike.crop(left=_loc.offset, right=strike.width-_loc.offset-_loc.width)
        for _loc in locs
    )
    glyphs = tuple(
        Glyph(_pix, codepoint=_ord, kerning=_kern, spacing=_spc)
        for _ord, (_pix, _kern, _spc) in enumerate(
            zip(pixels, kerning, spacing),
            start=props.tf_LoChar
        )
    )
    return glyphs


###################################################################################################
# convert from Amiga to monobit

def _convert_amiga_font(amiga_props, glyphs):
    """Convert Amiga properties and glyphs to monobit Font."""
    glyphs = _convert_amiga_glyphs(glyphs, amiga_props)
    props = _convert_amiga_props(amiga_props)
    return props, glyphs


def _convert_amiga_glyphs(glyphs, amiga_props):
    """Convert Amiga glyph properties to monobit."""
    # apply kerning and spacing
    glyphs = [
        _glyph.modify(
            left_bearing=_glyph.kerning,
            # baseline is the nth line, counting from the top, starting with 0
            # so if there are 8 lines and baseline == 6 then that's 1 line from the bottom
            shift_up=1-(amiga_props.tf_YSize - amiga_props.tf_Baseline),
            #advance_width=_glyph.spacing
            right_bearing=_glyph.spacing-_glyph.width-_glyph.kerning,
        )
        for _glyph in glyphs
    ]
    glyphs = [
        _glyph.drop('kerning', 'spacing')
        for _glyph in glyphs
    ]
    # default glyph has no codepoint
    glyphs[-1] = glyphs[-1].modify(codepoint=(), tag='default')
    return glyphs


def _convert_amiga_props(amiga_props):
    """Convert AmigaFont properties into yaff properties."""
    if amiga_props.tf_Style.FSF_COLORFONT:
        raise UnsupportedError('Amiga ColorFont not supported')
    props = Props()
    name = bytes(amiga_props.dfh_Name).decode(_ENCODING).strip()
    if name:
        props.name = name
    props.revision = amiga_props.dfh_Revision
    # tf_Style
    if amiga_props.tf_Style.FSF_BOLD:
        props.weight = 'bold'
    if amiga_props.tf_Style.FSF_ITALIC:
        props.slant = 'italic'
    if amiga_props.tf_Style.FSF_EXTENDED:
        props.setwidth = 'expanded'
    if amiga_props.tf_Style.FSF_UNDERLINED:
        props.decoration = 'underline'
    # tf_Flags
    props.spacing = (
        'proportional' if amiga_props.tf_Flags.FPF_PROPORTIONAL else 'monospace'
    )
    if amiga_props.tf_Flags.FPF_REVPATH:
        props.direction = 'right-to-left'
    if amiga_props.tf_Flags.FPF_TALLDOT and not amiga_props.tf_Flags.FPF_WIDEDOT:
        # TALLDOT: This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
        props.pixel_aspect = '1 2'
    elif amiga_props.tf_Flags.FPF_WIDEDOT and not amiga_props.tf_Flags.FPF_TALLDOT:
        # WIDEDOT: This font was designed for a Lores Interlaced screen (320x400 NTSC)
        props.pixel_aspect = '2 1'
    props.encoding = _ENCODING
    props.default_char = 'default'
    props.bold_smear = amiga_props.tf_BoldSmear
    return props


###############################################################################
# Amiga writer

@savers.register(linked=load_amiga_fc)
def save_amiga_fc(fonts, outstream):
    """Save fonts to Amiga disk font contents (.FONT) file."""
    props = tuple(_convert_to_amiga_props(_f) for _f in fonts)
    # the size is the filename, so it muct be unique.
    # there is an assumption that all fonts in the pack are part of a family
    # but we leave it to the user to enforce this.
    dirname = Path(outstream.name).stem
    filenames = tuple(f'{dirname}/{_prop.tf_YSize}' for _prop in props)
    if len(set(filenames)) != len(fonts):
        raise UnsupportedError(
            'Each font in an Amiga font contents package must be different size.'
        )
    tagged_filenames = []
    file_id = _FCH_ID
    for font, filename in zip(fonts, filenames):
        with outstream.where.open(filename, mode='w') as f:
            save_amiga((font,), f)
        filename = filename.encode(_ENCODING).ljust(_MAXFONTPATH, b'\0')
        # store dpi in TFontContents
        if font.dpi is not None:
            tagbytes = b''.join((
                bytes(_TAG_ITEM(
                    ti_Tag=_TA_DEVICEDPI,
                    ti_Data_hi=font.dpi.x, ti_Data_lo=font.dpi.y,
                )),
                # TAG_DONE (truncated last 2 bytes)
                bytes(6),
                # tfc_TagCount = 2
                bytes(be.uint16(2)),
            ))
            # esnure zero-terminator before first tag
            filename = filename[:_MAXFONTPATH-len(tagbytes)-1] + b'\0' + tagbytes
            file_id = _TFCH_ID
        tagged_filenames.append(filename)
    fch = _FONT_CONTENTS_HEADER(
        fch_FileID=file_id,
        fch_NumEntries=len(fonts),
    )
    contentsarray = (_T_FONT_CONTENTS * len(fonts))(*(
        _T_FONT_CONTENTS(
            tfc_FileName=(be.uint8*(_MAXFONTPATH-2))(*_filename[:-2]),
            tfc_TagCount=be.uint16.from_bytes(filename[-2:]),
            tfc_YSize=_props.tf_YSize,
            tfc_Style=_props.tf_Style,
            tfc_Flags=_props.tf_Flags,
        )
        for _f, _props, _filename in zip(fonts, props, tagged_filenames)
    ))
    outstream.write(bytes(fch))
    outstream.write(bytes(contentsarray))


@savers.register(linked=load_amiga)
def save_amiga(fonts, outstream):
    """Write Amiga font file."""
    font = ensure_single(fonts)
    # font = font.equalise_horizontal()
    default = font.get_default_glyph()
    font = font.resample(encoding=_ENCODING, missing=None)
    # all amiga font's I've seen explicitly fill out the missing glyphs
    # rather than using the loc table to point to the default glyph
    font = make_contiguous(font, missing='default')
    if font.levels > 2:
        raise ValueError('Greyscale fonts not supported')
    # get range of glyphs, mark missing with sentinel
    coderange = range(
        int(min(font.get_codepoints())),
        int(max(font.get_codepoints())) + 1,
    )
    glyphs = [font.get_glyph(_cp, missing=None) for _cp in coderange]
    glyphs.append(default)
    # equalise glyph heights and upshifts (only; don't touch bearings)
    add_shift_up = max(0, -min(_g.shift_up for _g in glyphs))
    glyphs = tuple(
        _g.expand(
            # bring all glyphs to same height
            top=max(0, font.line_height - _g.height - _g.shift_up - add_shift_up),
            # expand by positive shift to make all upshifts equal
            bottom=_g.shift_up + add_shift_up,
        )
        for _g in glyphs
    )
    # create font strike
    strike_raster = Raster.concatenate(*(_g.pixels for _g in glyphs if _g))
    # word-align strike
    strike_raster = strike_raster.expand(right=(16-strike_raster.width)%16)
    fontData = strike_raster.as_bytes()
    # create width-offset table
    widths = tuple(_g.width if _g else 0 for _g in glyphs)
    offsets = accumulate(widths, initial=0)
    fontLoc = b''.join(
        bytes(_LOC_ENTRY(offset=_offset, width=_width))
        for _width, _offset in zip(widths, offsets)
    )
    fontSpace = bytes((be.int16 * len(glyphs))(*(
        _g.advance_width for _g in glyphs
    )))
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    # > On the Amiga, kerning refers
    # > to the number pixels to leave blank before rendering a glyph.
    fontKern =  bytes((be.int16 * len(glyphs))(*(
        _g.left_bearing for _g in glyphs
    )))
    # generate headers
    # hunk_size is number of 4-byte words after the last hunk_size field
    # which doubles as the nextSegment field below
    anchor = _AMIGA_HEADER.size - 4
    hunk_size, padding = divmod((
            anchor+len(fontData)+len(fontLoc)+len(fontSpace)+len(fontKern)
        ), 4
    )
    if padding:
        hunk_size += 1
    file_header = (
        # hunk id
        bytes(be.uint32(_HUNK_HEADER))
        # empty list (resident library names)
        + bytes(be.uint32(0))
        + bytes(_HUNK_FILE_HEADER_1(table_size=1, first_hunk=0, last_hunk=0))
        + bytes(be.uint32(hunk_size))
    )
    props = _convert_to_amiga_props(font)
    font_header = _AMIGA_HEADER(
        dfh_NextSegment=hunk_size,
        dfh_ReturnCode=_RETURN_CODE,
        dfh_ln_Type=_NT_FONT,
        dfh_ln_Name=_NAME_POINTER,
        dfh_FileID=_DFH_ID,
        tf_ln_Type=_NT_FONT,
        tf_ln_Name=_NAME_POINTER,
        **vars(props),
        tf_LoChar=int(min(font.get_codepoints())),
        tf_HiChar=int(max(font.get_codepoints())),
        tf_CharData=anchor,
        tf_Modulo=strike_raster.width // 8,
        tf_CharLoc=anchor + len(fontData),
        tf_CharSpace=anchor + len(fontData) + len(fontLoc),
        tf_CharKern=anchor + len(fontData) + len(fontLoc) + len(fontSpace),
    )
    # write out
    outstream.write(file_header)
    outstream.write(bytes(be.uint32(_HUNK_CODE)))
    outstream.write(bytes(font_header))
    outstream.write(fontData)
    outstream.write(fontLoc)
    outstream.write(fontSpace)
    outstream.write(fontKern)
    outstream.write(bytes(padding))
    outstream.write(bytes(be.uint32(_HUNK_END)))


def _convert_to_amiga_props(font):
    """Convert font properties to amiga header fields."""
    return Props(
        dfh_Revision=int(font.revision),
        dfh_Name=font.name[:_MAXFONTNAME].encode(_ENCODING, 'replace'),
        tf_YSize=font.glyphs[0].height,
        tf_Style=_TF_STYLE(
            FSF_BOLD=font.weight == 'bold',
            FSF_ITALIC=font.slant == 'italic',
            FSF_EXTENDED=font.setwidth == 'expanded',
            FSF_UNDERLINED='underline' in font.decoration,
            # dpi tags are stored in the Font Contents file
            # but we need to set this flag to signal they exist
            FSF_TAGGED=font.dpi is not None,
        ),
        tf_Flags=_TF_FLAGS(
            FPF_DESIGNED=1,
            FPF_DISKFONT=1,
            FPF_PROPORTIONAL=font.spacing not in ('character-cell', 'monospace'),
            FPF_REVPATH=font.direction == 'right_to_left',
            FPF_TALLDOT=font.pixel_aspect.y > font.pixel_aspect.x,
            FPF_WIDEDOT=font.pixel_aspect.x > font.pixel_aspect.y,
        ),
        tf_XSize=int(font.average_width),
        # shift_up=1-(amiga_props.tf_YSize - amiga_props.tf_Baseline)
        tf_Baseline=font.glyphs[0].shift_up + font.glyphs[0].height - 1,
        tf_BoldSmear=font.bold_smear,
    )
