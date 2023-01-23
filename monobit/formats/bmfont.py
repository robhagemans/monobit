"""
monobit.bmfont - AngelCode BMFont format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import json
import shlex
import logging
from pathlib import Path
import xml.etree.ElementTree as etree

try:
    from PIL import Image
except ImportError:
    Image = None

from ..basetypes import Coord
from ..encoding import charmaps
from .. import streams
from ..streams import FileFormatError
from ..binary import int_to_bytes, bytes_to_int
from ..struct import little_endian as le
from ..properties import reverse_dict
from ..storage import loaders, savers
from ..font import Font, Coord
from ..glyph import Glyph
from ..labels import Codepoint, Char

from .windows import CHARSET_MAP, CHARSET_REVERSE_MAP


##############################################################################

# text/xml/binary format: https://www.angelcode.com/products/bmfont/doc/file_format.html
# json format: https://github.com/Jam3/load-bmfont/blob/master/json-spec.md

##############################################################################
# top-level calls

if Image:
    @loaders.register('bmf', name='bmfont')
    def load_bmfont(infile, where, outline:bool=False):
        """
        Load fonts from Angelcode BMFont format.

        outline: extract outline layer instead of glyph layer
        """
        return _read_bmfont(infile, where, outline)

    @savers.register(linked=load_bmfont)
    def save(
            fonts, outfile, where,
            image_size:Coord=(256, 256),
            image_format:str='png',
            packed:bool=True,
            descriptor:str='text',
        ):
        """
        Save fonts to Angelcode BMFont format.

        image_size: pixel width,height of the spritesheet(s) storing the glyphs (default: 256x256)
        image_format: image format of the spritesheets (default: 'png')
        packed: if true, use each of the RGB channels as a separate spritesheet (default: True)
        descriptor: font descriptor file format, one of 'text', 'json' (default: 'text')
        """
        if len(fonts) > 1:
            raise FileFormatError("Can only save one font to BMFont file.")
        _create_bmfont(outfile, where, fonts[0], image_size, packed, image_format, descriptor)


##############################################################################
# BMFont spec
# see http://www.angelcode.com/products/bmfont/doc/file_format.html

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


# info struct

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

# common struct

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

def _pages(npages, size):
    strlen = size // npages
    return le.Struct(
        pageNames=(le.char * strlen) * int(npages)
    )


# char struct

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


# kerning struct

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
        raise ValueError(
            f'Not a valid BMFont XML file: root should be <font>, not <{root.tag}>'
        )
    for tag in ('info', 'common', 'pages', 'chars'):
        if root.find(tag) is None:
            raise ValueError(
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
        ],
    return result

def _parse_json(data):
    """Parse JSON bmfont description."""
    # https://github.com/Jam3/load-bmfont/blob/master/json-spec.md
    tree = json.loads(data)
    for tag in ('info', 'common', 'pages', 'chars'):
        if tag not in tree:
            raise ValueError(
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
            logging.warning('All glyphs are blank.')
            # only one colour found
            bg, fg = colourset[0], None
            # note that if colourset is empty, all char widths/heights must be zero
        elif len(colourset) > 2:
            raise ValueError(
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
        'source-format':
            'BMFont ({} descriptor; {} spritesheet)'.format(bmformat, ','.join(imgformats)),
        'source-name': Path(name).name,
        'family': bmfont_props.pop('face'),
        'line-height': common.lineHeight,
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


def _read_bmfont(infile, container, outline):
    """Read a bmfont from a container."""
    magic = infile.peek(3)
    fontinfo = {}
    if magic.startswith(b'BMF'):
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

def _glyph_id(glyph, encoding):
    if charmaps.is_unicode(encoding):
        char = glyph.char
        if len(char) > 1:
            raise ValueError(
                f"Can't store multi-codepoint grapheme sequence {ascii(char)}."
            )
        return ord(char)
    if not glyph.codepoint:
        raise ValueError(f"Can't store glyph with no codepoint: {glyph}.")
    else:
        return bytes_to_int(glyph.codepoint)


def _create_spritesheets(font, size=(256, 256), packed=False):
    """Dump font to sprite sheets."""
    # use all channels
    if not packed:
        channels = 15
        n_layers = 1
    else:
        n_layers = 4
    paper = 0
    ink = 255
    border = 0
    width, height = size
    chars = []
    pages = []
    empty = Image.new('L', (width, height), border)
    sheets = [empty] * n_layers
    pages.append(sheets)
    page_id = 0
    layer = 0
    while True:
        if packed:
            channels = 1 << layer
        img = Image.new('L', (width, height), border)
        sheets[layer] = img
        # output glyphs
        x, y = 0, 0
        tree = SpriteNode(x, y, width, height)
        for number, glyph in enumerate(font.glyphs):
            cropped = glyph.reduce()
            if cropped.height and cropped.width:
                try:
                    x, y = tree.insert(cropped)
                except ValueError:
                    # we don't fit, get next sheet
                    break
                charimg = Image.new('L', (cropped.width, cropped.height))
                data = cropped.as_vector(ink, paper)
                charimg.putdata(data)
                img.paste(charimg, (x, y))
            try:
                id = _glyph_id(glyph, font.encoding)
            except ValueError as e:
                logging.warning(e)
                continue
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
            chars.append(dict(
                id=id,
                x=x,
                y=y,
                width=cropped.width,
                height=cropped.height,
                # > The `xoffset` gives the horizontal offset that should be added to the cursor
                # > position to find the left position where the character should be drawn.
                # > A negative value here would mean that the character slightly overlaps
                # > the previous character.
                xoffset=cropped.left_bearing,
                # > The `yoffset` gives the distance from the top of the cell height to the top
                # > of the character. A negative value here would mean that the character extends
                # > above the cell height.
                yoffset=font.raster.top-(cropped.height+cropped.shift_up),
                # xadvance is the advance width from origin to next origin
                # > The filled red dot marks the current cursor position, and the hollow red dot
                # > marks the position of the cursor after drawing the character. You get to this
                # > position by moving the cursor horizontally with the xadvance value.
                # > If kerning pairs are used the cursor should also be moved accordingly.
                xadvance=cropped.advance_width,
                page=page_id,
                chnl=channels,
            ))
        else:
            # iterator runs out, get out
            break
        # move to next layer or page
        if layer == n_layers - 1:
            page_id += 1
            layer = 0
            sheets = [empty] * n_layers
            pages.append(sheets)
        else:
            layer += 1
    if packed:
        # bmfont channel order is B, G, R, A
        pages = [Image.merge('RGBA', [_sh[2], _sh[1], _sh[0], _sh[3]]) for _sh in pages]
    else:
        pages = [Image.merge('RGBA', _sh*4) for _sh in pages]
    return pages, chars


def _to_str(value):
    """Convert value to str for bmfont file."""
    if isinstance(value, str) :
        return '"{}"'.format(value)
    if isinstance(value, (list, tuple)):
        return ','.join(str(_item) for _item in value)
    return str(int(value))

def _create_textdict(name, dict):
    """Create a text-dictionary line for bmfontfile."""
    return '{} {}\n'.format(name, ' '.join(
        '{}={}'.format(_k, _to_str(_v))
        for _k, _v in dict.items())
    )

def _create_bmfont(
        outfile, container, font,
        size=(256, 256), packed=False, imageformat='png', descriptor='text'
    ):
    """Create a bmfont package."""
    path = Path('.') / font.family
    fontname = font.name.replace(' ', '_')
    encoding = font.encoding
    if not charmaps.is_unicode(encoding):
        # if encoding is unknown, call it OEM
        charset = _CHARSET_STR_REVERSE_MAP.get(encoding, _CHARSET_STR_REVERSE_MAP[''])
        # ensure codepoint values are set
        font = font.label(codepoint_from=encoding)
    else:
        charset = ''
        # ensure char values are set
        font = font.label(char_from=encoding)
    # create images
    pages, chars = _create_spritesheets(font, size, packed)
    props = {}
    props['chars'] = chars
    # save images; create page table
    # https://www.angelcode.com/products/bmfont/doc/file_format.html
    #
    # >  page
    # >  ----
    # >  This tag gives the name of a texture file. There is one for each page in the font.
    # >  id     The page id.
    # >  file   The texture file name.
    props['pages'] = []
    for page_id, page in enumerate(pages):
        name = container.unused_name(f'{path}/{fontname}_{page_id}', imageformat)
        with container.open(name, 'w') as imgfile:
            page.save(imgfile, format=imageformat)
        props['pages'].append({
            'id': page_id,
            'file': name
        })
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
        'unicode': charmaps.is_unicode(encoding),
        'stretchH': 100,
        'smooth': False,
        'aa': 1,
        'padding': (0, 0, 0, 0),
        'spacing': (0, 0),
        'outline': 0,
    }
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
        'scaleW': size[0],
        'scaleH': size[1],
        'pages': len(pages),
        'packed': packed,
        'alphaChnl': 0,
        'redChnl': 0,
        'greenChnl': 0,
        'blueChnl': 0,
    }
    # >  kerning
    # >  -------
    # >  The kerning information is used to adjust the distance between certain characters, e.g.
    # >  some characters should be placed closer to each other than others.
    # >  first  The first character id.
    # >  second The second character id.
    # >  amount	How much the x position should be adjusted when drawing the second character
    # >  immediately following the first.
    props['kernings'] = [{
            'first': _glyph_id(_glyph, font.encoding),
            'second': _glyph_id(font.get_glyph(_to), font.encoding),
            'amount': int(_amount)
        }
        for _glyph in font.glyphs
        for _to, _amount in _glyph.right_kerning.items()
    ]
    # write the .fnt description
    if descriptor == 'text':
        _write_fnt_descriptor(outfile, props, chars)
    elif descriptor == 'json':
        _write_json(outfile, props, chars)
    else:
        raise FileFormatError(f'Writing to descriptor format {format} not supported.')

def _write_fnt_descriptor(outfile, props, chars):
    """Write the .fnt descriptor file."""
    bmf = outfile.text
    bmf.write(_create_textdict('info', props['info']))
    bmf.write(_create_textdict('common', props['common']))
    for page in props['pages']:
        bmf.write(_create_textdict('page', page))
    bmf.write('chars count={}\n'.format(len(chars)))
    for char in chars:
        bmf.write(_create_textdict('char', char))
    bmf.write('kernings count={}\n'.format(len(props['kernings'])))
    for kern in props['kernings']:
        bmf.write(_create_textdict('kerning', kern))

def _write_json(outfile, props, chars):
    """Write JSON bmfont description."""
    tree = {**props}
    # assume the pages list is ordered
    tree['pages'] = [_elem['file'] for _elem in tree['pages']]
    tree['chars'] = chars
    json.dump(tree, outfile.text)


class SpriteNode:
    """Tree structure to fill up spritesheet."""
    # see http://blackpawn.com/texts/lightmaps/

    def __init__(self, left, top, right, bottom):
        """Create a new node."""
        self._left, self._top, self._right, self._bottom = left, top, right, bottom
        self._children = None
        self._image = None

    def insert(self, img):
        """Insert an image into this node or descendant node."""
        width = self._right - self._left
        height = self._bottom - self._top
        if self._children:
            try:
                return self._children[0].insert(img)
            except ValueError:
                return self._children[1].insert(img)
        if self._image or img.width > width or img.height > height:
            raise ValueError("Image doesn't fit.")
        if img.width == width and img.height == height:
            self._image = img
            return self._left, self._top
        else:
            dw = width - img.width
            dh = height - img.height
            if dw > dh:
                self._children = (
                    SpriteNode(self._left, self._top, self._left + img.width, self._bottom),
                    SpriteNode(self._left + img.width, self._top, self._right, self._bottom)
                )
            else:
                self._children = (
                    SpriteNode(self._left, self._top, self._right, self._top + img.height),
                    SpriteNode(self._left, self._top + img.height, self._right, self._bottom)
                )
            return self._children[0].insert(img)
