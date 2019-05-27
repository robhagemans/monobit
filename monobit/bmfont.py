"""
monobit.bmfont - AngelCode BMFont format

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import json
import shlex
import logging
import xml.etree.ElementTree as etree

try:
    from PIL import Image
except ImportError:
    Image = None

from .base import ZipContainer
from .binary import friendlystruct
from .typeface import Typeface
from .font import Font, Label
from .glyph import Glyph
from .winfnt import _CHARSET_MAP



##############################################################################
# top-level calls

if Image:
    @Typeface.loads('bmfzip', name='BMFont', encoding=None)
    def load(instream):
        """Load fonts from bmfont in zip container."""
        with ZipContainer(instream, 'r') as zipfile:
            descriptions = [
                _name for _name in zipfile.namelist()
                if _name.lower().endswith(('.fnt', '.json', '.xml'))
            ]
            fonts = [_read_bmfont(zipfile, desc) for desc in descriptions]
        return Typeface(fonts)

    @Typeface.saves('bmfzip', encoding=None, multi=True)
    def save(typeface, outstream, size=(256, 256), packed=True, imageformat='png'):
        """Save fonts to bmfonts in zip container."""
        with ZipContainer(outstream, 'w') as container:
            for font in typeface._fonts:
                _create_bmfont(container, font, size, packed, imageformat)


##############################################################################
# BMFont spec
# see http://www.angelcode.com/products/bmfont/doc/file_format.html

_HEAD = friendlystruct(
    'le',
    magic='3s',
    version='uint8',
)

_BLKHEAD = friendlystruct(
    'le',
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
    return friendlystruct(
        'le',
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
        fontName = friendlystruct.char * (size-14),
    )

# info bitfield
_INFO_BOLD = 1 << 3
_INFO_ITALIC = 1 << 2
_INFO_UNICODE = 1 << 1
_INFO_SMOOTH = 1 << 0

# BMFont charset constants seem to be undocumented, but a list is here:
# https://github.com/vladimirgamalyan/fontbm/blob/master/src/FontInfo.cpp
# looks like these are equal to the Windows OEM ones
# mapping of those is a guess, see _CHARSET_MAP in winfnt.py
_CHARSET_STR_MAP = {
    'ANSI': 'windows-1252',
    'DEFAULT': 'windows-1252', # ?
    'SYMBOL': 'symbol',
    'MAC': 'mac-roman',
    'SHIFTJIS': 'windows-932',
    'HANGUL': 'windows-949',
    'JOHAB': 'johab',
    'GB2312': 'windows-936',
    'CHINESEBIG5': 'windows-950',
    'GREEK': 'windows-1253',
    'TURKISH': 'windows-1254',
    'VIETNAMESE': 'windows-1258',
    'HEBREW': 'windows-1255',
    'ARABIC': 'windows-1256',
    'BALTIC': 'windows-1257',
    'RUSSIAN': 'windows-1251',
    'THAI': 'windows-874',
    'EASTEUROPE': 'windows-1250',
    'OEM': 'cp437', # ?
}


# common struct

_COMMON = friendlystruct(
    'le',
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
    return friendlystruct(
        'le',
        pageNames=(friendlystruct.char * strlen) * int(npages)
    )


# char struct

_CHAR = friendlystruct(
    'le',
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
    return friendlystruct(
        'le',
        chars=_CHAR * (size // _CHAR.size)
    )


# kerning struct

_KERNING = friendlystruct(
    'le',
    first='uint32',
    second='uint32',
    amount='int16',
)

def _kernings(size):
    return friendlystruct(
        'le',
        kernings=_KERNING * (size // _KERNING.size)
    )


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
            'Not a valid BMFont XML file: root should be <font>, not <{}>'.format(root.tag)
        )
    return dict(
        bmformat='xml',
        info=root.find('info').attrib,
        common=_COMMON(**_dict_to_ints(root.find('common').attrib)),
        pages=[_elem.attrib for _elem in root.find('pages').iterfind('page')],
        chars=[
            _CHAR(**_dict_to_ints(_elem.attrib))
            for _elem in root.find('chars').iterfind('char')
        ],
        kernings=[
            _KERNING(**_dict_to_ints(_elem.attrib))
            for _elem in root.find('kernings').iterfind('kerning')
        ],
    )

def _parse_json(data):
    """Parse JSON bmfont description."""
    # https://github.com/Jam3/load-bmfont/blob/master/json-spec.md
    tree = json.loads(data)
    return dict(
        bmformat='json',
        info=tree['info'],
        common=_COMMON(**_dict_to_ints(tree['common'])),
        pages=[{'id': _i, 'file': _page} for _i, _page in enumerate(tree['pages'])],
        chars=[_CHAR(**_dict_to_ints(_elem)) for _elem in tree['chars']],
        kernings=[_KERNING(**_dict_to_ints(_elem)) for _elem in tree['kernings']],
    )

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
        'charset': _CHARSET_MAP.get(bininfo.charSet, ''),
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

def _extract(zipfile, path, bmformat, info, common, pages, chars, kernings=()):
    """Extract characters."""
    sheets = {
        int(_page['id']): Image.open(zipfile.open(os.path.join(path, _page['file']), 'rb'))
        for _page in pages
    }
    imgformats = set(str(_img.format) for _img in sheets.values())
    # ensure we have RGBA channels
    sheets = {_k: _v.convert('RGBA') for _k, _v in sheets.items()}
    glyphs = []
    labels = {}
    min_after = 0
    if chars:
        # determine bearings
        min_after = min((char.xadvance - char.xoffset - char.width) for char in chars)
        min_before = min((char.xoffset) for char in chars)
        max_height = max(char.height + char.yoffset for char in chars)
        # outline channel
        if 1 in (common.redChnl, common.greenChnl, common.blueChnl, common.alphaChnl):
            logging.warning('Outline channel not preserved.')
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
            masks = (
                bool(char.chnl & _CHNL_R) and common.redChnl in (0, 2),
                bool(char.chnl & _CHNL_G) and common.greenChnl in (0, 2),
                bool(char.chnl & _CHNL_B) and common.blueChnl in (0, 2),
                bool(char.chnl & _CHNL_A) and common.alphaChnl in (0, 2),
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
        # check if font is monochromatic
        colourset = list(set(_tup for _sprite in sprites for _tup in _sprite))
        if len(colourset) == 1:
            logging.warning('All glyphs are empty.')
            # only one colour found
            bg, fg = colourset[0], None
            # note that if colourset is empty, all char widths/heights must be zero
        elif len(colourset) > 2:
            raise ValueError(
                'Greyscale, colour and antialiased fonts not supported.'
            )
        elif len(colourset) == 2:
            # use highesr intensity (sum of channels) as foreground
            bg, fg = colourset
            if sum(bg) > sum(fg):
                bg, fg = fg, bg
        # extract glyphs
        for char, sprite in zip(chars, sprites):
            if char.width and char.height:
                bits = tuple(_c == fg for _c in sprite)
                glyph = Glyph(tuple(
                    bits[_offs: _offs+char.width]
                    for _offs in range(0, len(bits), char.width)
                ))
                after = char.xadvance - char.xoffset - char.width
                before = char.xoffset
                height = char.height + char.yoffset
                # bring to equal height, equal bearings
                glyph = glyph.expand(
                    before - min_before, char.yoffset, after - min_after, max_height - height
                )
            else:
                glyph = Glyph.empty(char.xadvance - min_after, max_height)
            labels[char.id] = len(glyphs)
            glyphs.append(glyph)
    # parse properties
    bmfont_props = {**info}
    # encoding
    if _to_int(bmfont_props.pop('unicode')):
        encoding = 'unicode'
    else:
        # if props are from binary, this has already been converted through _CHARSET_MAP
        charset = bmfont_props.pop('charset')
        encoding = _CHARSET_STR_MAP.get(charset.upper(), charset)
    properties = {
        'source-format': 'BMFont ({} .fnt; {} sprites)'.format(bmformat, ','.join(imgformats)),
        'bearing-after': min_after,
        'family': bmfont_props.pop('face'),
        'pixel-size': bmfont_props.pop('size'),
        'weight': 'bold' if _to_int(bmfont_props.pop('bold')) else 'regular',
        'slant': 'italic' if _to_int(bmfont_props.pop('italic')) else 'roman',
        'encoding': encoding,
        'kerning': '\n'.join(
            '{} {} {}'.format(Label(_kern.first), Label(_kern.second), _kern.amount)
            for _kern in kernings
        ),
        # TODO: offset from common.base
    }
    properties.update({'bmfont.' + _k: _v for _k, _v in bmfont_props.items()})
    return Font(glyphs, labels, (), properties)

def _read_bmfont(container, name):
    """Read a bmfont from a container."""
    with container.open(name, 'rb') as fnt:
        magic = fnt.read(3)
    fontinfo = {}
    try:
        if magic == b'BMF':
            logging.debug('found binary: %s', name)
            with container.open(name, 'rb') as fnt:
                fontinfo = _parse_binary(fnt.read())
        else:
            with container.open(name, 'r') as fnt:
                for line in fnt:
                    if line:
                        break
                data = line + '\n' + fnt.read()
                if line.startswith('<'):
                    logging.debug('found xml: %s', name)
                    fontinfo = _parse_xml(data)
                elif line.startswith('{'):
                    logging.debug('found json: %s', name)
                    fontinfo = _parse_json(data)
                else:
                    logging.debug('found text: %s', name)
                    fontinfo = _parse_text(data)
        path = os.path.dirname(name)
        return _extract(container, path, **fontinfo)
    except Exception as e:
        logging.error('Could not extract %s: %s', name, e)

##############################################################################
# bmfont writer

def _create_spritesheets(font, size=(256, 256), packed=False):
    """Dump font to sprite sheets."""
    # use all channels
    if not packed:
        channels = 15
        n_layers = 1
    else:
        n_layers = 4
    back = 0
    fore = 255
    border = 0
    width, height = size
    chars = []
    pages = []
    empty = Image.new('L', (width, height), border)
    sheets = [empty] * n_layers
    pages.append(sheets)
    iter_unicode = font.iter_unicode()
    page_id = 0
    layer = 0
    while True:
        if packed:
            channels = 1 << layer
        img = Image.new('L', (width, height), border)
        sheets[layer] = img
        # output glyphs
        x, y = 0, 0
        next_x, next_y = 0, 0
        for label, glyph in iter_unicode:
            if glyph.height and glyph.width:
                if next_x + glyph.width > width:
                    x, y = 0, next_y
                else:
                    x = next_x
                if y + glyph.height > height:
                    # next sheet
                    break
                # put sequentially in straight rows, we can be clever some other time
                next_y = max(y + glyph.height, next_y)
                charimg = Image.new('L', (glyph.width, glyph.height))
                data = glyph.as_tuple(fore, back)
                charimg.putdata(data)
                img.paste(charimg, (x, y))
                next_x = x + glyph.width
            chars.append(dict(
                id=int(label[2:], 16),
                x=x,
                y=y,
                width=glyph.width,
                height=glyph.height,
                xoffset=font.bearing_before,
                yoffset=font.bounding_box.y - glyph.height, #-font.offset - glyph.height,
                # not sure how these are really interpreted
                xadvance=font.bearing_before + glyph.width + font.bearing_after,
                page=page_id,
                chnl=channels,
            ))
        else:
            # iter_unicode runs out, get out
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

def _create_bmfont(container, font, size=(256, 256), packed=False, imageformat='png'):
    """Create a bmfont package."""
    path = font.family
    fontname = font.name.replace(' ', '_')
    # create images
    pages, chars = _create_spritesheets(font, size, packed)
    props = {}
    props['chars'] = chars
    # save images; create page table
    props['pages'] = []
    for page_id, page in enumerate(pages):
        name = '{}_{}.{}'.format(fontname, page_id, imageformat)
        with container.open(os.path.join(path, name), 'wb') as imgfile:
            page.save(imgfile, format=imageformat)
        props['pages'].append({'id': page_id, 'file': name})
    props['info'] = {
        'face': font.family,
        'size': font.pixel_size,
        'bold': font.weight == 'bold',
        'italic': font.slant in ('italic', 'oblique'),
        'charset': '',
        'unicode': True,
        'stretchH': 100,
        'smooth': False,
        'aa': 1,
        'padding': (0, 0, 0, 0),
        'spacing': (0, 0),
        'outline': 0,
    }
    props['common'] = {
        'lineHeight': font.bounding_box.y + font.leading,
        'base': font.bounding_box.y + font.offset,
        'scaleW': size[0],
        'scaleH': size[1],
        'pages': len(pages),
        'packed': packed,
        'alphaChnl': 0,
        'redChnl': 0,
        'greenChnl': 0,
        'blueChnl': 0,
    }
    if hasattr(font, 'kerning'):
        # FIXME: we're saving glyphs iterating over unicode, but this table has ordinal labels...
        props['kernings'] = [{
                'first': int(_first, 0),
                'second': int(_second, 0),
                'amount': int(_amount)
            }
            for _kernline in font.kerning.splitlines()
            for _first, _second, _amount in _kernline.split()
        ]
    else:
        props['kernings'] = []
    # write the .fnt description
    bmfontname = '{}.fnt'.format(fontname)
    with container.open(os.path.join(path, bmfontname), 'w') as bmf:
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
