"""
monobit.bmfont - read and write bmfont pacakages

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

_KERNING = friendlystruct(
    'le',
    first='uint32',
    second='uint32',
    amount='int16',
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
            if data[:3] == b'BMF':
                logging.info('found binary: %s', desc)
                #fontinfo = _parse_binary(data)
            else:
                for line in data.splitlines():
                    if line:
                        break
                if line.decode('utf-8-sig').strip().startswith('<?xml'):
                    logging.info('found xml: %s', desc)
                    fontinfo = _parse_xml(data)
                else:
                    logging.info('found text: %s', desc)
                    #fontinfo = _parse_text(data)
            if fontinfo:
                fonts.append(_extract(zipfile, **fontinfo))
        return Typeface(fonts)


def _parse_xml(data):
    """Parse XML bmfont description."""
    root = etree.fromstring(data.decode('utf-8-sig'))
    #root = tree.getroot()
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

def _extract(zipfile, info, common, pages, chars, kernings):
    """Extract characters."""
    sheets = {
        int(_page['id']): Image.open(zipfile.open(_page['file'])).convert('RGBA')
        for _page in pages
    }
    #sheets[0].show()
    glyphs = []
    labels = {}
    # determine bearings
    min_after = min((char.xadvance - char.width) for char in chars)
    max_height = max(char.height for char in chars)
    for char in chars:
        crop = sheets[char.page].crop((
            char.x, char.y, char.x + char.width, char.y + char.height
        ))
        masks = [bool(char.chnl&4), bool(char.chnl&2), bool(char.chnl&1), bool(char.chnl&8)]
        if char.width and char.height:
            # require fully saturated - we could set a threshold here
            crop = tuple(
                all((not _mask or (_pix==255)) for _pix, _mask in zip(_rgba, masks))
                for _rgba in crop.getdata()
            )
            glyph = Glyph(tuple(
                crop[_offs: _offs+char.width]
                for _offs in range(0, len(crop), char.width)
            ))
            after = char.xadvance - char.width
            # bring to equal height, equal bearings
            glyph = glyph.expand(0, max_height - char.height, after - min_after, 0)
        else:
            glyph = Glyph.empty(char.xadvance - min_after, max_height)
        labels[char.id] = len(glyphs)
        glyphs.append(glyph)
    # parse properties
    bmfont_props = {**info, **common}
    properties = {
        'bearing-after': min_after,
        'family': bmfont_props.pop('face'),
        'pixel-size': bmfont_props.pop('size'),
        'weight': 'bold' if bmfont_props.pop('bold') == '1' else 'regular',
        'slant': 'italic' if bmfont_props.pop('italic') == '1' else 'roman',
        'encoding': 'unicode' if bmfont_props.pop('unicode') else bmfont_props.pop('charset'),
    }
    properties.update({'bmfont.' + _k: _v for _k, _v in bmfont_props.items()})
    return Font(glyphs, labels, (), properties)
