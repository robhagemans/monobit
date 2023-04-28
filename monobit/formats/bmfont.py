"""
monobit.formats.bmfont - AngelCode BMFont format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import json
import shlex
import logging
from pathlib import Path
import xml.etree.ElementTree as etree
from math import ceil, sqrt
from itertools import zip_longest

try:
    from PIL import Image
except ImportError:
    Image = None

from ..basetypes import Coord, Bounds
from ..encoding import charmaps
from .. import streams
from ..magic import FileFormatError
from ..binary import int_to_bytes, bytes_to_int, ceildiv
from ..struct import little_endian as le
from ..properties import Props, reverse_dict
from ..storage import loaders, savers
from ..font import Font, Coord
from ..glyph import Glyph
from ..labels import Codepoint, Char
from ..chart import grid_map
from ..glyphmap import GlyphMap

from .windows import CHARSET_MAP, CHARSET_REVERSE_MAP


# text/xml/binary format: https://www.angelcode.com/products/bmfont/doc/file_format.html
# json format: https://github.com/Jam3/load-bmfont/blob/master/json-spec.md

_BMF_MAGIC = b'BMF'


##############################################################################
# top-level calls

if Image:
    # the magic is optional - only for binary descriptor file
    @loaders.register(
        name='bmfont',
        magic=(
            _BMF_MAGIC,
            b'info',
            b'<?xml version="1.0"?>\n<font>',
            b'<?xml version="1.0"?>\r\n<font>',
        ),
        patterns=('*.fnt',),
    )
    def load_bmfont(infile, outline:bool=False):
        """
        Load fonts from Angelcode BMFont format.

        outline: extract outline layer instead of glyph layer
        """
        return _read_bmfont(infile, outline)

    @savers.register(linked=load_bmfont)
    def save(
            fonts, outfile, *,
            image_size:Coord=None,
            image_format:str='png',
            grid:bool=False,
            packed:bool=True,
            spacing:Coord=Coord(0, 0),
            padding:Bounds=Bounds(0, 0, 0, 0),
            descriptor:str='text',
        ):
        """
        Save fonts to Angelcode BMFont format.

        image_size: pixel width,height of the spritesheet(s) storing the glyphs (default: estimate)
        image_format: image format of the spritesheets (default: 'png')
        packed: if true, use each of the RGB channels as a separate spritesheet (default: True)
        grid: if true, use grid image instead of spritesheet (default: False)
        spacing: x,y spacing between individual glyphs (default: 0x0)
        padding: left, top, right, bottom unused spacing around edges (default: 0,0,0,0)
        descriptor: font descriptor file format, one of 'text', 'json' (default: 'text')
        """
        if len(fonts) > 1:
            raise FileFormatError("Can only save one font to BMFont file.")
        _create_bmfont(
            outfile, fonts[0],
            size=image_size, packed=packed, grid=grid,
            spacing=spacing, padding=padding,
            image_format=image_format, descriptor=descriptor
        )


##############################################################################
# BMFont spec
# see http://www.angelcode.com/products/bmfont/doc/file_format.html

# file and block headers for binary file

_HEAD = le.Struct(
    magic='3s',
    version='uint8',
)

_BLKHEAD = le.Struct(
    typeId='uint8',
    blkSize='uint32',
)

# type ids
_BLK_INFO = 1
_BLK_COMMON = 2
_BLK_PAGES = 3
_BLK_CHARS = 4
_BLK_KERNINGS = 5


# info section - binary and text/xml/json formats diverge slightly
#
# > info
# > ----
# > This tag holds information on how the font was generated.
# > face        This is the name of the true type font.
# > size        The size of the true type font.
# > bold        The font is bold.
# > italic      The font is italic.
# > charset     The name of the OEM charset used (when not unicode).
# > unicode     Set to 1 if it is the unicode charset.
# > stretchH    The font height stretch in percentage. 100% means no stretch.
# > smooth      Set to 1 if smoothing was turned on.
# > aa          The supersampling level used. 1 means no supersampling was used.
# > padding     The padding for each character (up, right, down, left).
# > spacing     The spacing for each character (horizontal, vertical).
# > outline     The outline thickness for the characters.

def _info(size):
    return le.Struct(
        fontSize='int16',
        bitField='uint8',
        charSet='uint8',
        stretchH='uint16',
        aa='uint8',
        paddingUp='uint8',
        paddingRight='uint8',
        paddingDown='uint8',
        paddingLeft='uint8',
        spacingHoriz='uint8',
        spacingVert='uint8',
        outline='uint8',
        fontName = le.char * (size-14),
    )

# info bitfield
_INFO_BOLD = 1 << 3
_INFO_ITALIC = 1 << 2
_INFO_UNICODE = 1 << 1
_INFO_SMOOTH = 1 << 0

# BMFont charset constants seem to be undocumented, but a list is here:
# https://github.com/vladimirgamalyan/fontbm/blob/master/src/FontInfo.cpp
# looks like these are equal to the Windows OEM ones
# mapping of those is a guess, see CHARSET_MAP in windows.py
_CHARSET_NUM_MAP = {
    'ANSI': 0x00,
    'DEFAULT': 0x01,
    'SYMBOL':  0x02,
    'MAC': 0x4d,
    'SHIFTJIS': 0x80,
    'HANGUL': 0x81,
    'JOHAB': 0x82,
    'GB2312': 0x86,
    'CHINESEBIG5': 0x88,
    'GREEK': 0xa1,
    'TURKISH': 0xa2,
    'VIETNAMESE': 0xa3,
    'HEBREW': 0xb1,
    'ARABIC': 0xb2,
    'BALTIC': 0xba,
    'RUSSIAN': 0xcc,
    'THAI': 0xde,
    'EASTEUROPE': 0xee,
    'OEM': 0xff,
}
_CHARSET_NUM_REVERSE_MAP = reverse_dict(_CHARSET_NUM_MAP)

_CHARSET_STR_MAP = {
    _str: CHARSET_MAP[_num]
    for _str, _num in _CHARSET_NUM_MAP.items()
}
_CHARSET_STR_REVERSE_MAP = reverse_dict(_CHARSET_STR_MAP)

# common section
#
# > common
# > ------
# > This tag holds information common to all characters.
# > lineHeight  This is the distance in pixels between each line of text.
# > base        The number of pixels from the absolute top of the line to the base of the characters.
# > scaleW      The width of the texture, normally used to scale the x pos of the character image.
# > scaleH      The height of the texture, normally used to scale the y pos of the character image.
# > pages       The number of texture pages included in the font.
# > packed      Set to 1 if the monochrome characters have been packed into each of the texture
# >             channels. In this case alphaChnl describes what is stored in each channel.
# > alphaChnl   Set to 0 if the channel holds the glyph data, 1 if it holds the outline,
# >             2 if it holds the glyph and the outline, 3 if its set to zero,
# >             and 4 if its set to one.
# > redChnl     ..(value as alphaChnl)..
# > greenChnl   ..(value as alphaChnl)..
# > blueChnl    ..(value as alphaChnl)..

_COMMON = le.Struct(
    lineHeight='uint16',
    base='uint16',
    scaleW='uint16',
    scaleH='uint16',
    pages='uint16',
    # spec says next field is bitField, with 0-6 reserved, 7 packed
    # but this choice aligns text formats with binary, and we can use as bool in either case
    packed='uint8',
    alphaChnl='uint8',
    redChnl='uint8',
    greenChnl='uint8',
    blueChnl='uint8',
)

# page tag
# part of common struct in binary file

# https://www.angelcode.com/products/bmfont/doc/file_format.html
#
# >  page
# >  ----
# >  This tag gives the name of a texture file. There is one for each page in the font.
# >  id     The page id.
# >  file   The texture file name.

def _pages(npages, size):
    strlen = size // npages
    return le.Struct(
        pageNames=(le.char * strlen) * int(npages)
    )


# char struct
#
# >  char
# >  ----
# >  This tag describes on character in the font. There is one for each included character in the font.
# >  id         The character id.
# >  x          The left position of the character image in the texture.
# >  y          The top position of the character image in the texture.
# >  width      The width of the character image in the texture.
# >  height     The height of the character image in the texture.
# >  xoffset    How much the current position should be offset when copying the image from the texture to the screen.
# >  yoffset    How much the current position should be offset when copying the image from the texture to the screen.
# >  xadvance   How much the current position should be advanced after drawing the character.
# >  page       The texture page where the character image is found.
# >  chnl       The texture channel where the character image is found (1 = blue, 2 = green, 4 = red, 8 = alpha, 15 = all channels).

_CHAR = le.Struct(
    id='uint32',
    x='uint16',
    y='uint16',
    width='uint16',
    height='uint16',
    xoffset='int16',
    yoffset='int16',
    xadvance='int16',
    page='uint8',
    chnl='uint8',
)

# channel bitfield
_CHNL_R = 1 << 2
_CHNL_G = 1 << 1
_CHNL_B = 1 << 0
_CHNL_A = 1 << 3


def _chars(size):
    return le.Struct(
        chars=_CHAR * (size // _CHAR.size)
    )


# kerning section
#
# >  kerning
# >  -------
# >  The kerning information is used to adjust the distance between certain characters, e.g.
# >  some characters should be placed closer to each other than others.
# >  first  The first character id.
# >  second The second character id.
# >  amount	How much the x position should be adjusted when drawing the second character
# >  immediately following the first.

_KERNING = le.Struct(
    first='uint32',
    second='uint32',
    amount='int16',
)

def _kernings(size):
    return le.Struct(
        kernings=_KERNING * (size // _KERNING.size)
    )


# common settings for unparsed informational properties
# these document the rasteriser/spritesheet generator settings of the AngelFont converter
_UNPARSED_PROPS = {
    # > stretchH    The font height stretch in percentage. 100% means no stretch.
    'stretchH': '100',
    # > smooth      Set to 1 if smoothing was turned on.
    'smooth': '0',
    # > aa          The supersampling level used. 1 means no supersampling was used.
    'aa': '1',
    # > padding     The padding for each character (up, right, down, left).
    'padding': '0,0,0,0',
    # > spacing     The spacing for each character (horizontal, vertical).
    'spacing': '0,0',
    # > outline     The outline thickness for the characters.
    'outline': '0',
}


##############################################################################
# bmfont readers

def _to_int(value):
    """Convert str or numeric value to int."""
    if isinstance(value, str):
        value = value.lower()
    if value == 'true':
        return 1
    elif value == 'false':
        return 0
    else:
        return int(value)

def _dict_to_ints(strdict):
    """Convert all dict values to int."""
    return {_k: _to_int(_attr) for _k, _attr in strdict.items()}

def _parse_xml(data):
    """Parse XML bmfont description."""
    root = etree.fromstring(data)
    if root.tag != 'font':
        raise FileFormatError(
            f'Not a valid BMFont XML file: root should be <font>, not <{root.tag}>'
        )
    for tag in ('info', 'common', 'pages', 'chars'):
        if root.find(tag) is None:
            raise FileFormatError(
                f'Not a valid BMFont XML file: no <{tag}> tag found.'
            )
    result = dict(
        bmformat='xml',
        info=root.find('info').attrib,
        common=_COMMON(**_dict_to_ints(root.find('common').attrib)),
        pages=[_elem.attrib for _elem in root.find('pages').iterfind('page')],
        chars=[
            _CHAR(**_dict_to_ints(_elem.attrib))
            for _elem in root.find('chars').iterfind('char')
        ],
        kernings=[]
    )
    if root.find('kernings') is not None:
        result['kernings'] = [
            _KERNING(**_dict_to_ints(_elem.attrib))
            for _elem in root.find('kernings').iterfind('kerning')
        ]
    return result

def _parse_json(data):
    """Parse JSON bmfont description."""
    # https://github.com/Jam3/load-bmfont/blob/master/json-spec.md
    tree = json.loads(data)
    for tag in ('info', 'common', 'pages', 'chars'):
        if tag not in tree:
            raise FileFormatError(
                f'Not a valid BMFont JSON file: no <{tag}> key found.'
            )
    result = dict(
        bmformat='json',
        info=tree['info'],
        common=_COMMON(**_dict_to_ints(tree['common'])),
        pages=[{'id': _i, 'file': _page} for _i, _page in enumerate(tree['pages'])],
        chars=[_CHAR(**_dict_to_ints(_elem)) for _elem in tree['chars']],
        kernings=[]
    )
    if 'kernings' in tree:
        result['kernings'] = [_KERNING(**_dict_to_ints(_elem)) for _elem in tree['kernings']]
    return result

def _parse_text_dict(line):
    """Parse space separated key=value pairs."""
    textdict = dict(_item.split('=') for _item in shlex.split(line) if _item)
    return {
        _key: _value
        for _key, _value in textdict.items()
    }

def _parse_text(data):
    """Parse text bmfont description."""
    fontinfo = {
        'bmformat': 'text',
        'pages': [],
        'chars': [],
        'kernings': [],
    }
    for line in data.splitlines():
        if not line or ' ' not in line:
            continue
        tag, textdict = line.split(' ', 1)
        textdict = _parse_text_dict(textdict)
        if tag == 'info':
            fontinfo[tag] = textdict
        if tag == 'common':
            fontinfo[tag] = _COMMON(**_dict_to_ints(textdict))
        elif tag == 'page':
            fontinfo['pages'].append(textdict)
        elif tag == 'char':
            fontinfo['chars'].append(
                _CHAR(**_dict_to_ints(textdict))
            )
        elif tag == 'kerning':
            fontinfo['kernings'].append(
                _KERNING(**_dict_to_ints(textdict))
            )
    return fontinfo


def _parse_binary(data):
    """Parse binary bmfont description."""
    head = _HEAD.from_bytes(data, 0)
    offset = _HEAD.size
    props = {'bmformat': 'binary'}
    while offset < len(data):
        blkhead = _BLKHEAD.from_bytes(data, offset)
        if blkhead.typeId == _BLK_INFO:
            blk = _info(blkhead.blkSize)
            tag = 'info'
        elif blkhead.typeId == _BLK_COMMON:
            blk = _COMMON
            tag = 'common'
        elif blkhead.typeId == _BLK_PAGES:
            # info block must precede pages block?
            blk = _pages(props['common'].pages, blkhead.blkSize)
            tag = 'pages'
        elif blkhead.typeId == _BLK_CHARS:
            blk = _chars(blkhead.blkSize)
            tag = 'chars'
        elif blkhead.typeId == _BLK_KERNINGS:
            blk = _kernings(blkhead.blkSize)
            tag = 'kernings'
        props[tag] = blk.from_bytes(data, offset + _BLKHEAD.size)
        offset += _BLKHEAD.size + blk.size
    bininfo = props['info']
    props['info'] = {
        'face': bininfo.fontName.decode('ascii', 'replace'),
        'size': bininfo.fontSize,
        'bold': bininfo.bitField & _INFO_BOLD,
        'italic': bininfo.bitField & _INFO_ITALIC,
        'unicode': bininfo.bitField & _INFO_UNICODE,
        'smooth': bininfo.bitField & _INFO_SMOOTH,
        'charset': CHARSET_MAP.get(bininfo.charSet, ''),
        'aa': bininfo.aa,
        'padding': ','.join((
            str(bininfo.paddingUp), str(bininfo.paddingRight),
            str(bininfo.paddingDown), str(bininfo.paddingLeft)
        )),
        'spacing': ','.join((str(bininfo.spacingHoriz), str(bininfo.spacingVert))),
        'outline': bininfo.outline,
    }
    props['pages'] = [
        {'id': str(_id), 'file': bytes(_name).decode('ascii', 'ignore').split('\0')[0]}
        for _id, _name in enumerate(props['pages'].pageNames)
    ]
    props['chars'] = props['chars'].chars
    if 'kernings' in props:
        props['kernings'] = props['kernings'].kernings
    else:
        props['kernings'] = []
    return props

def _extract(container, name, bmformat, info, common, pages, chars, kernings=(), outline=False):
    """Extract glyphs."""
    path = Path(name).parent
    image_files = {
        int(_page['id']): container.open(path / _page['file'], 'r')
        for _page in pages
    }
    sheets = {_id: Image.open(_file) for _id, _file in image_files.items()}
    imgformats = set(str(_img.format) for _img in sheets.values())
    # ensure we have RGBA channels
    sheets = {_k: _v.convert('RGBA') for _k, _v in sheets.items()}
    glyphs = []
    if chars:
        # extract channel masked sprites
        sprites = []
        for char in chars:
            crop = sheets[char.page].crop((
                char.x, char.y, char.x + char.width, char.y + char.height
            ))
            # deal with faulty .fnt's
            if not char.chnl:
                char.chnl = 15
            # keep only channels that hold this char
            # drop any zeroed/oned channels and the outline channel
            if outline:
                channels = (1, 2)
            else:
                channels = (0, 2)
            masks = (
                bool(char.chnl & _CHNL_R) and common.redChnl in channels,
                bool(char.chnl & _CHNL_G) and common.greenChnl in channels,
                bool(char.chnl & _CHNL_B) and common.blueChnl in channels,
                bool(char.chnl & _CHNL_A) and common.alphaChnl in channels,
            )
            if char.width and char.height:
                # require all glyph channels above threshold
                imgdata = crop.getdata()
                masked = tuple(
                    tuple(_pix for _pix, _mask in zip(_rgba, masks) if _mask)
                    for _rgba in imgdata
                )
            else:
                masked = ()
            sprites.append(masked)
        # close resources
        for image in sheets.values():
            image.close()
        # check if font is monochromatic
        colourset = list(set(_tup for _sprite in sprites for _tup in _sprite))
        if len(colourset) <= 1:
            # only one colour found
            bg, fg = None, colourset[0]
            # note that if colourset is empty, all char widths/heights must be zero
        elif len(colourset) > 2:
            raise FileFormatError(
                'Greyscale, colour and antialiased fonts not supported.'
            )
        elif len(colourset) == 2:
            # use higher intensity (sum of channels) as foreground
            bg, fg = colourset
            if sum(bg) > sum(fg):
                bg, fg = fg, bg
        # extract glyphs
        for char, sprite in zip(chars, sprites):
            #if char.width and char.height:
            bits = tuple(_c == fg for _c in sprite)
            if not char.width:
                glyph = Glyph.blank(width=0, height=char.height)
            else:
                glyph = Glyph(tuple(
                    bits[_offs: _offs+char.width]
                    for _offs in range(0, len(bits), char.width)
                ))
            # append kernings (this glyph left)
            is_unicode = bool(_to_int(info['unicode']))
            if is_unicode:
                labeller = lambda _id: Char(chr(_id))
            else:
                labeller = lambda _id: Codepoint(_id)
            right_kerning = {
                labeller(_kern.second): _kern.amount
                for _kern in kernings
                if _kern.first == char.id
            }
            glyph = glyph.modify(
                labels=(labeller(char.id),),
                left_bearing=char.xoffset,
                right_bearing=char.xadvance - char.xoffset - char.width,
                right_kerning=right_kerning
            )
            glyphs.append(glyph)
    for file in image_files.values():
        file.close()
    # convert to yaff properties
    properties = _parse_bmfont_props(
        name, bmformat, imgformats, info, common,
    )
    # > The `yoffset` gives the distance from the top of the cell height to the top
    # > of the character. A negative value here would mean that the character extends
    # > above the cell height.
    # pylint: disable=no-member
    raster_top = Font(glyphs, **properties).raster.top
    glyphs = [
        _glyph.modify(
            shift_up=raster_top-_glyph.height-_char.yoffset,
        )
        for _glyph, _char in zip(glyphs, chars)
    ]
    font = Font(glyphs, **properties)
    font = font.label()
    return font


def _parse_bmfont_props(name, bmformat, imgformats, info, common):
    # parse properties
    bmfont_props = {**info}
    # encoding
    if _to_int(bmfont_props.pop('unicode')):
        encoding = 'unicode'
        bmfont_props.pop('charset')
    else:
        # if props are from binary, this has already been converted through CHARSETMAP
        charset = bmfont_props.pop('charset')
        encoding = _CHARSET_STR_MAP.get(charset.upper(), charset)
    properties = {
        'source_format':
            'BMFont ({} descriptor; {} spritesheet)'.format(bmformat, ','.join(imgformats)),
        'source_name': Path(name).name,
        'family': bmfont_props.pop('face'),
        'line_height': common.lineHeight,
        # shift-up is set per-glyph
        'encoding': encoding,
    }
    if _to_int(bmfont_props.pop('bold')):
        properties['weight'] = 'bold'
    if _to_int(bmfont_props.pop('italic')):
        properties['slant'] = 'italic'
    # drop other props if they're default value
    bmfont_props = {
        _k: _v for _k, _v in bmfont_props.items()
        if str(_v) != _UNPARSED_PROPS.get(_k, '')
    }
    properties['bmfont'] = ' '.join(
        f'{_k}=' + ','.join(str(_v).split(','))
        for _k, _v in bmfont_props.items()
    )
    return properties


def _read_bmfont(infile, outline):
    """Read a bmfont from a container."""
    container = infile.where
    magic = infile.peek(3)
    fontinfo = {}
    if magic.startswith(_BMF_MAGIC):
        logging.debug('found binary: %s', infile.name)
        fontinfo = _parse_binary(infile.read())
    else:
        fnt = infile.text
        line = ''
        for line in fnt:
            if line:
                break
        data = line + '\n' + fnt.read()
        if line.startswith('<'):
            logging.debug('found xml: %s', fnt.name)
            fontinfo = _parse_xml(data)
        elif line.startswith('{'):
            logging.debug('found json: %s', fnt.name)
            fontinfo = _parse_json(data)
        else:
            logging.debug('found text: %s', fnt.name)
            fontinfo = _parse_text(data)
    return _extract(container, infile.name, outline=outline, **fontinfo)



##############################################################################
##############################################################################
# bmfont writer

def _create_bmfont(
        outfile, font, *,
        size, packed, grid, spacing, padding,
        image_format, descriptor,
        paper=0, ink=255, border=0,
    ):
    """Create a bmfont package."""
    # ensure codepoint/char values are set as appropriate
    encoding = font.encoding
    if not charmaps.is_unicode(encoding):
        font = font.label(codepoint_from=encoding)
    else:
        font = font.label(char_from=encoding)
    # map glyphs to image
    if grid:
        margin  = Coord(padding.left, padding.top)
        glyph_map = grid_map(
            font,
            columns=32, margin=margin, padding=spacing,
            # direction - note Image coordinates are ltr, ttb
            order='row-major', direction=(1, 1),
        )
    else:
        # crop glyphs
        glyphs = tuple(_g.reduce() for _g in font.glyphs)
        if size is None:
            n_layers = 4 if packed else 1
            size = _estimate_size(glyphs, n_layers, padding, spacing)
        glyph_map = spritesheet(
            glyphs, size=size, spacing=spacing, padding=padding,
        )
    # draw images
    sheets = _draw_images(glyph_map, packed, paper, ink, border)
    # save images and record names
    pages = _save_pages(outfile, font, sheets, image_format)
    # create the descriptor data structure
    width, height  = sheets[0].width, sheets[0].height
    props = _convert_to_bmfont(
        font, pages, glyph_map, width, height, packed, padding, spacing
    )
    # write the descriptor file
    if descriptor == 'text':
        _write_text_descriptor(outfile, props)
    elif descriptor == 'json':
        _write_json_descriptor(outfile, props)
    elif descriptor == 'xml':
        _write_xml_descriptor(outfile, props)
    elif descriptor == 'binary':
        _write_binary_descriptor(outfile, props)
    else:
        raise FileFormatError(
            'Descriptor format should be one of `test`, `xml`, `binary`, `json`;'
            f' `{format}` not recognised.'
        )


def _convert_to_bmfont(
        font, pages, glyph_map,
        width, height, packed, padding, spacing
    ):
    """Convert to bmfont property structure."""
    props = {}
    props['chars'] = [
        dict(
            id=_glyph_id(_entry.glyph, font.encoding),
            x=_entry.x,
            y=_entry.y,
            width=_entry.glyph.width,
            height=_entry.glyph.height,
            # > The `xoffset` gives the horizontal offset that should be added to the cursor
            # > position to find the left position where the character should be drawn.
            # > A negative value here would mean that the character slightly overlaps
            # > the previous character.
            xoffset=_entry.glyph.left_bearing,
            # > The `yoffset` gives the distance from the top of the cell height to the top
            # > of the character. A negative value here would mean that the character extends
            # > above the cell height.
            yoffset=font.raster.top-(_entry.glyph.height+_entry.glyph.shift_up),
            # xadvance is the advance width from origin to next origin
            # > The filled red dot marks the current cursor position, and the hollow red dot
            # > marks the position of the cursor after drawing the character. You get to this
            # > position by moving the cursor horizontally with the xadvance value.
            # > If kerning pairs are used the cursor should also be moved accordingly.
            xadvance=_entry.glyph.advance_width,
            page=_entry.sheet // 4 if packed else _entry.sheet,
            chnl=(1 << (_entry.sheet%4)) if packed else 15,
        )
        for _entry in glyph_map
        if _glyph_id(_entry.glyph, font.encoding) >= 0
    ]
    # save images; create page table
    props['pages'] = pages
    # info section
    if not charmaps.is_unicode(font.encoding):
        # if encoding is unknown, call it OEM
        charset = _CHARSET_STR_REVERSE_MAP.get(
            font.encoding, _CHARSET_STR_REVERSE_MAP['']
        )
    else:
        charset = ''
    props['info'] = {
        'face': font.family,
        # size can be given as negative for an undocumented reason:
        #
        # https://gamedev.net/forums/topic/657937-strange-34size34-of-generated-bitmapfont/5161902/
        # > The 'info' block is just a little information on the original truetype font used to
        # > generate the bitmap font. This is normally not used while rendering the text.
        # > A negative size here reflects that the size is matching the cell height, rather than
        # > the character height.
        #
        # we're assuming size == pixel-size == ascent + descent
        # so it should be positive - negative means matching "cell height" (~ font.raster_size.y ?)
        'size': font.pixel_size,
        'bold': font.weight == 'bold',
        'italic': font.slant in ('italic', 'oblique'),
        'charset': charset,
        'unicode': charmaps.is_unicode(font.encoding),
        'stretchH': 100,
        'smooth': False,
        'aa': 1,
        'padding': tuple(padding),
        'spacing': tuple(spacing),
        'outline': 0,
    }
    # common section
    props['common'] = {
        # https://www.angelcode.com/products/bmfont/doc/render_text.html
        # > [...] the lineHeight, i.e. how far the cursor should be moved vertically when
        # > moving to the next line.
        'lineHeight': font.line_height,
        # "base" is the distance between top-line and baseline
        # > The base value is how far from the top of the cell height the base of the characters
        # > in the font should be placed. Characters can of course extend above or below this base
        # > line, which is entirely up to the font design.
        'base': font.raster.top,
        'scaleW': width,
        'scaleH': height,
        'pages': len(pages),
        'packed': packed,
        'alphaChnl': 0,
        'redChnl': 0,
        'greenChnl': 0,
        'blueChnl': 0,
    }
    # kerning section
    kerningtable = [
        (_glyph, font.get_glyph(_to), _amount)
        for _glyph in font.glyphs
        for _to, _amount in _glyph.right_kerning.items()
    ]
    kerningtable.extend(
        (font.get_glyph(_to), _glyph, _amount)
        for _glyph in font.glyphs
        for _to, _amount in _glyph.left_kerning.items()
    )
    kerningtable = (
        (_glyph_id(_l, font.encoding), _glyph_id(_r, font.encoding), int(_amt))
        for _l, _r, _amt in kerningtable
    )
    # exclude unsupported ids
    props['kernings'] = tuple(
        {
            'first': _left,
            'second': _right,
            'amount': _amount,
        }
        for _left, _right, _amount in kerningtable
        if _left >= 0 and _right >= 0
    )
    return props


def _glyph_id(glyph, encoding):
    if charmaps.is_unicode(encoding):
        char = glyph.char
        if len(char) > 1:
            logging.warning(
                f"Can't store multi-codepoint grapheme sequence {ascii(char)}."
            )
            return -1
        if not char:
            return -1
        return ord(char)
    if not glyph.codepoint:
        logging.warning(f"Can't store glyph with no codepoint: {glyph}.")
        return -1
    else:
        return bytes_to_int(glyph.codepoint)


###############################################################################
# text descriptor files

def _write_text_descriptor(outfile, props):
    """Write a text-based .fnt descriptor file."""
    bmf = outfile.text
    bmf.write(_create_textdict('info', props['info']))
    bmf.write(_create_textdict('common', props['common']))
    for page in props['pages']:
        bmf.write(_create_textdict('page', page))
    bmf.write('chars count={}\n'.format(len(props['chars'])))
    for char in props['chars']:
        bmf.write(_create_textdict('char', char))
    bmf.write('kernings count={}\n'.format(len(props['kernings'])))
    for kern in props['kernings']:
        bmf.write(_create_textdict('kerning', kern))

def _create_textdict(name, dict):
    """Create a text-dictionary line for bmfontfile."""
    return '{} {}\n'.format(name, ' '.join(
        '{}={}'.format(_k, _to_str(_v))
        for _k, _v in dict.items())
    )

def _to_str(value):
    """Convert value to str for bmfont file."""
    if isinstance(value, str) :
        return '"{}"'.format(value)
    if isinstance(value, (list, tuple)):
        return ','.join(str(_item) for _item in value)
    return str(int(value))


###############################################################################
# json, xml descriptor files

def _write_json_descriptor(outfile, props):
    """Write JSON bmfont description."""
    tree = {**props}
    # assume the pages list is ordered
    tree['pages'] = [_elem['file'] for _elem in tree['pages']]
    json.dump(tree, outfile.text)

def _write_xml_descriptor(outfile, props):
    """Write XML bmfont description."""
    tree = {**props}
    # convert values to str
    def _tostrdict(indict):
        return {_k: str(_v) for _k, _v in indict.items()}
    root = etree.Element('font')
    etree.SubElement(root, 'info', **_tostrdict(tree['info']))
    etree.SubElement(root, 'common', **_tostrdict(tree['common']))
    pages =etree.SubElement(root, 'pages')
    for elem in tree['pages']:
        etree.SubElement(pages, 'page', **_tostrdict(elem))
    chars = etree.SubElement(root, 'chars', count=str(len(props['chars'])))
    for char in props['chars']:
        etree.SubElement(chars, 'char', **_tostrdict(char))
    if props['kernings']:
        kerns = etree.SubElement(root, 'kernings', count=str(len(props['kernings'])))
        for kern in props['kernings']:
            etree.SubElement(kerns, 'kerning', **_tostrdict(kern))
    outfile.write(b'<?xml version="1.0"?>\n')
    etree.ElementTree(root).write(outfile)


###############################################################################
# binary descriptor files

def _write_binary_descriptor(outfile, props):
    """Write binary bmfont description."""
    head = _HEAD(magic=b'BMF', version=3)
    outfile.write(bytes(head))
    # INFO section
    info = props['info']
    pages = props['pages']
    padding = Bounds.create(info['padding'])
    spacing = Coord.create(info['spacing'])
    bininfo = dict(
        fontName=info['face'].encode('ascii', 'replace') + b'\0',
        fontSize=info['size'],
        bitField=(
            (_INFO_BOLD if info['bold'] else 0)
            | (_INFO_ITALIC if info['italic'] else 0)
            | (_INFO_UNICODE if info['unicode'] else 0)
            | (_INFO_SMOOTH if info['smooth'] else 0)
        ),
        charset=CHARSET_REVERSE_MAP.get(info['charset'], 0xff),
        aa=info['aa'],
        paddingUp=padding.top,
        paddingLeft=padding.left,
        paddingDown=padding.bottom,
        paddingRight=padding.right,
        spacingHoriz=spacing.x,
        spacingVert=spacing.y,
        outline=info['outline'],
    )
    infosize = len(bininfo['fontName']) + 14
    infoblk = bytes(_info(infosize)(**bininfo))
    outfile.write(bytes(_BLKHEAD(typeId=_BLK_INFO, blkSize=infosize)))
    outfile.write(infoblk)
    # COMMON section
    commonblk = bytes(_COMMON(**props['common']))
    outfile.write(bytes(_BLKHEAD(typeId=_BLK_COMMON, blkSize=len(commonblk))))
    outfile.write(commonblk)
    # PAGES section
    binpages = b''.join((
        _page['file'].encode('ascii', 'replace') + b'\0'
        for _page in pages
    ))
    outfile.write(bytes(_BLKHEAD(typeId=_BLK_PAGES, blkSize=len(binpages))))
    outfile.write(binpages)
    # CHARS section
    binchars = b''.join(bytes(_CHAR(**_c)) for _c in props['chars'])
    outfile.write(bytes(_BLKHEAD(typeId=_BLK_CHARS, blkSize=len(binchars))))
    outfile.write(binchars)
    # KERNINGS section
    binkerns = b''.join(bytes(_KERNING(**_c)) for _c in props['kernings'])
    outfile.write(bytes(_BLKHEAD(typeId=_BLK_KERNINGS, blkSize=len(binkerns))))
    outfile.write(binkerns)


###############################################################################
# image files

def _save_pages(outfile, font, sheets, image_format):
    """Save images and record names."""
    container = outfile.where
    basepath = Path(outfile.name).parent
    path = basepath / font.family
    fontname = font.name.replace(' ', '_')
    pages = []
    for page_id, sheet in enumerate(sheets):
        name = container.unused_name(f'{path}/{fontname}_{page_id}.{image_format}')
        with container.open(name, 'w') as imgfile:
            sheet.save(imgfile, format=image_format)
        pages.append({
            'id': page_id,
            'file': str(Path(name).relative_to(basepath)),
        })
    return pages


###############################################################################
# draw spritesheets

def _draw_images(glyph_map, packed, paper, ink, border):
    """Draw images based on glyph map."""
    images = glyph_map.to_images(
        paper=paper, ink=ink, border=border,
        invert_y=True, transparent=False
    )
    width, height = images[0].width, images[0].height
    # pack 4 sheets per image in RGBA layers
    if packed:
        # grouper: quartets, fill with empties
        empty = Image.new('L', (width, height), border)
        args = [iter(images)] * 4
        quartets = zip_longest(*args, fillvalue=empty)
        return tuple(
            # bmfont channel order is B, G, R, A
            Image.merge('RGBA', (_q[2], _q[1], _q[0], _q[3]))
            for _q in quartets
        )
    return images


###############################################################################
# packed spritesheets

def spritesheet(glyphs, *, size, spacing, padding):
    """Determine where to draw glyphs in sprite sheets."""
    # sort by area, large to small. keep mapping table
    sorted_glyphs = tuple(sorted(
        enumerate(glyphs),
        key=lambda _p: _p[1].width*_p[1].height,
        reverse=True,
    ))
    order_mapping = {_p[0]: _index for _index, _p in enumerate(sorted_glyphs)}
    glyphs = tuple(_p[1] for _p in sorted_glyphs)
    # determine spritesheet size
    width, height = size
    use_width = width-padding.left-padding.right
    use_height = height-padding.top-padding.bottom
    spx, spy = spacing
    # ensure sheet is larger than largest glyph
    if any(
            _g.width + spx > use_width or _g.height + spy > use_height
            for _g in glyphs
        ):
        raise ValueError('Image size is too small for largest glyph.')
    glyph_map = GlyphMap()
    sheets = []
    while True:
        # output glyphs
        sheets.append(SpriteNode(0, 0, use_width, use_height, depth=0))
        for number, glyph in enumerate(glyphs):
            if glyph.height and glyph.width:
                for i, sheet in enumerate(sheets):
                    try:
                        x, y = sheet.insert(glyph.width+spx, glyph.height+spy)
                        break
                    except (FullError, DoesNotFitError):
                        pass
                else:
                    # we don't fit, get next sheet
                    glyphs = glyphs[number:]
                    break
            glyph_map.append_glyph(
                glyph, x+padding.left, y+padding.top, sheet=i
            )
        else:
            # all done, get out
            break
    # put chars in original glyph order
    glyph_map.reorder(order_mapping)
    return glyph_map


def _estimate_size(glyphs, n_layers, padding, spacing):
    """Estimate required size of sprite sheet."""
    max_width = max(_g.width for _g in glyphs)
    max_height = max(_g.height for _g in glyphs)
    total_area = sum(
        (_g.width+spacing.x) * (_g.height+spacing.y)
        for _g in glyphs
    )
    edge = int(ceil(1.01 * sqrt(total_area / n_layers)))
    return Coord(
        max_width * ceildiv(edge, max_width) + padding.left + padding.right,
        max_height * ceildiv(edge, max_height) + padding.top + padding.bottom,
    )


class DoesNotFitError(Exception):
    """Image does not fit."""

class FullError(Exception):
    """Branch is full."""


class SpriteNode:
    """Tree structure to fill up spritesheet."""
    # see http://blackpawn.com/texts/lightmaps/

    def __init__(self, left, top, right, bottom, depth):
        """Create a new node."""
        self._left, self._top, self._right, self._bottom = left, top, right, bottom
        self._children = None
        self._full = False
        self._depth = depth

    def insert(self, target_width, target_height):
        """Insert an image into this node or descendant node."""
        width = self._right - self._left
        height = self._bottom - self._top
        if target_width > width or target_height > height:
            raise DoesNotFitError()
        if self._full:
            raise FullError()
        if self._children:
            try:
                return self._children[0].insert(target_width, target_height)
            except (DoesNotFitError, FullError) as e:
                pass
            try:
                return self._children[1].insert(target_width, target_height)
            except FullError as e:
                self._full = True
                raise
        if target_width == width and target_height == height:
            self._full = True
            return self._left, self._top
        else:
            dw = width - target_width
            dh = height - target_height
            if dw > dh:
                self._children = (
                    SpriteNode(self._left, self._top, self._left + target_width, self._bottom, self._depth+1),
                    SpriteNode(self._left + target_width, self._top, self._right, self._bottom, self._depth+1)
                )
            else:
                self._children = (
                    SpriteNode(self._left, self._top, self._right, self._top + target_height, self._depth+1),
                    SpriteNode(self._left, self._top + target_height, self._right, self._bottom, self._depth+1)
                )
            return self._children[0].insert(target_width, target_height)
