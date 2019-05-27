"""
monobit.bmfont - AngelCode BMFont format

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import io
from zipfile import ZipFile
import xml.etree.ElementTree as etree

try:
    from PIL import Image
except ImportError:
    Image = None

from .binary import friendlystruct
from .typeface import Typeface
from .font import Font, Label
from .glyph import Glyph
from .winfnt import _CHARSET_MAP


# BMFont spec
# http://www.angelcode.com/products/bmfont/doc/file_format.html



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


if Image:
    @Typeface.loads('bmfzip', name='BMFont', encoding=None)
    def load(instream):
        """Load fonts from bmfont in zip container."""
        zipfile = ZipFile(io.BytesIO(instream.read()))
        descriptions = [_name for _name in zipfile.namelist() if _name.lower().endswith('.fnt')]
        fonts = []
        for desc in descriptions:
            data = zipfile.open(desc, 'r').read()
            fontinfo = {}
            try:
                if data[:3] == b'BMF':
                    logging.debug('found binary: %s', desc)
                    fontinfo = _parse_binary(data)
                else:
                    for line in data.splitlines():
                        if line:
                            break
                    if line.decode('utf-8-sig').strip().startswith('<?xml'):
                        logging.debug('found xml: %s', desc)
                        fontinfo = _parse_xml(data)
                    else:
                        logging.debug('found text: %s', desc)
                        fontinfo = _parse_text(data)
                fonts.append(_extract(zipfile, **fontinfo))
            except Exception as e:
                logging.error('Could not extract %s: %s', desc, e)
        return Typeface(fonts)

def _to_int(value):
    """Convert str or int value to int."""
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
    root = etree.fromstring(data.decode('utf-8-sig'))
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


def _parse_text_dict(line):
    """Parse space separated key=value pairs."""
    textdict = dict(_item.split('=') for _item in line.split())
    return {
        _key: _value.strip('"')
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
    for line in data.decode('utf-8-sig').splitlines():
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

def _extract(zipfile, bmformat, info, common, pages, chars, kernings=()):
    """Extract characters."""
    sheets = {
        int(_page['id']): Image.open(zipfile.open(_page['file']))
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
    }
    properties.update({'bmfont.' + _k: _v for _k, _v in bmfont_props.items()})
    return Font(glyphs, labels, (), properties)
