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
from .font import Font
from .glyph import Glyph


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

_COMMON = friendlystruct(
    'le',
    lineHeight='uint16',
    base='uint16',
    scaleW='uint16',
    scaleH='uint16',
    pages='uint16',
    bitField='uint8',
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
                    logging.info('found binary: %s', desc)
                    fontinfo = _parse_binary(data)
                else:
                    for line in data.splitlines():
                        if line:
                            break
                    if line.decode('utf-8-sig').strip().startswith('<?xml'):
                        logging.info('found xml: %s', desc)
                        fontinfo = _parse_xml(data)
                    else:
                        logging.info('found text: %s', desc)
                        fontinfo = _parse_text(data)
            except Exception as e:
                logging.error('Could not extract %s: %s', desc, e)
            else:
                if fontinfo:
                    fonts.append(_extract(zipfile, **fontinfo))
        return Typeface(fonts)


def _parse_xml(data):
    """Parse XML bmfont description."""
    root = etree.fromstring(data.decode('utf-8-sig'))
    if root.tag != 'font':
        raise ValueError(
            'Not a valid BMFont XML file: root should be <font>, not <{}>'.format(root.tag)
        )
    return dict(
        info=root.find('info').attrib,
        common=root.find('common').attrib,
        pages=[_elem.attrib for _elem in root.find('pages').iterfind('page')],
        chars=[
            _CHAR(**{_k: int(_attr) for _k, _attr in _elem.attrib.items()})
            for _elem in root.find('chars').iterfind('char')
        ],
        kernings=[
            _KERNING(**{_k: int(_attr) for _k, _attr in _elem.attrib.items()})
            for _elem in root.find('kernings').iterfind('kerning')
        ],
    )


def _parse_text_dict(line):
    """Parse space separated key=value pairs."""
    textdict = dict(_item.split('=') for _item in line.split(' '))
    return {
        _key: _value.strip('"')
        for _key, _value in textdict.items()
    }

def _parse_text(data):
    """Parse text bmfont description."""
    fontinfo = {
        'pages': [],
        'chars': [],
        'kernings': [],
    }
    for line in data.decode('utf-8-sig').splitlines():
        if not line or ' ' not in line:
            continue
        tag, textdict = line.split(' ', 1)
        textdict = _parse_text_dict(textdict)
        if tag in ('info', 'common'):
            fontinfo[tag] = textdict
        elif tag == 'page':
            fontinfo['pages'].append(textdict)
        elif tag == 'char':
            fontinfo['chars'].append(
                _CHAR(**{_k: int(_attr) for _k, _attr in textdict.items()})
            )
        elif tag == 'kerning':
            fontinfo['kernings'].append(
                _KERNING(**{_k: int(_attr) for _k, _attr in textdict.items()})
            )
    return fontinfo


def _parse_binary(data):
    """Parse binary bmfont description."""
    head = _HEAD.from_bytes(data, 0)
    offset = _HEAD.size
    props = {}
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
        'bold': bininfo.bitField & 8,
        'italic': '1' if bininfo.bitField & 4 else '0',
        'unicode': '1' if bininfo.bitField & 2 else '0',
        'smooth': '1' if bininfo.bitField & 1 else '0',
        'charset': bininfo.charSet,
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
    return props

def _extract(zipfile, info, common, pages, chars, kernings=()):
    """Extract characters."""
    sheets = {
        int(_page['id']): Image.open(zipfile.open(_page['file'])).convert('RGBA')
        for _page in pages
    }
    glyphs = []
    labels = {}
    min_after = 0
    if chars:
        # determine bearings
        min_after = min((char.xadvance - char.xoffset - char.width) for char in chars)
        min_before = min((char.xoffset) for char in chars)
        max_height = max(char.height + char.yoffset for char in chars)
        for char in chars:
            crop = sheets[char.page].crop((
                char.x, char.y, char.x + char.width, char.y + char.height
            ))
            masks = [bool(char.chnl&4), bool(char.chnl&2), bool(char.chnl&1), bool(char.chnl&8)]
            if char.width and char.height:
                # require fully saturated - we could set a threshold here
                crop = tuple(
                    all((not _mask or (_pix>127)) for _pix, _mask in zip(_rgba, masks))
                    for _rgba in crop.getdata()
                )
                glyph = Glyph(tuple(
                    crop[_offs: _offs+char.width]
                    for _offs in range(0, len(crop), char.width)
                ))
                after = char.xadvance - char.xoffset - char.width
                before = char.xoffset
                height = char.height + char.yoffset
                # bring to equal height, equal bearings
                glyph = glyph.expand(before - min_before, char.yoffset, after - min_after, max_height - height)
            else:
                glyph = Glyph.empty(char.xadvance - min_after, max_height)
            labels[char.id] = len(glyphs)
            glyphs.append(glyph)
    # parse properties
    bmfont_props = {**info} #, **common}
    properties = {
        'bearing-after': min_after,
        'family': bmfont_props.pop('face'),
        'pixel-size': bmfont_props.pop('size'),
        'weight': 'bold' if bmfont_props.pop('bold') == '1' else 'regular',
        'slant': 'italic' if bmfont_props.pop('italic') == '1' else 'roman',
        'encoding': 'unicode' if bmfont_props.pop('unicode') == '1' else bmfont_props.pop('charset'),
    }
    properties.update({'bmfont.' + _k: _v for _k, _v in bmfont_props.items()})
    # TODO: preserve kerning pairs
    return Font(glyphs, labels, (), properties)
