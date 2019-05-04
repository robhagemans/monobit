"""
monobit.text - read and write hexdraw and yaff files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .base import ensure_stream, Font, Glyph


_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters

# default background characters
_BACK = "_.-"
# for now, anything else is foreground
#_FORE = '@#*'

# default order of known properties
PROPERTIES = [
    'name',
    'foundry',
    'copyright',
    'notice',
    'revision',
    'size',
    'family',
    'weight',
    'slant',
    'setwidth',
    'style',
    'direction',
    'spacing',
    'bottom',
    'offset-before',
    'offset-after',
    'dpi',
    'encoding',
    'default-char',
    'converter',
    'source-name',
    'source-format',
]


@Font.loads('text', 'txt', 'draw', 'yaff')
def load(infile, back=_BACK):
    """Read a plaintext font file."""
    with ensure_stream(infile, 'r', encoding='utf-8-sig') as instream:
        lines = list(instream)
        comments = [
            _line[1:].rstrip('\r\n')
            for _line in lines
            if _line.rstrip('\r\n') and _line[0] not in _CODESTART
        ]
        if all(_line.startswith(' ') for _line in comments):
            comments = [_line[1:] for _line in comments]
        # drop all comments
        codelines = [
            _line
            for _line in lines
            if _line and _line[0] in _CODESTART
        ]
        # cluster by character
        # assuming only one code point per glyph, for now
        clusters = []
        for line in codelines:
            if line[0] not in _WHITESPACE:
                cp, rest = line.strip().split(':', 1)
                if rest:
                    clusters.append((cp, [rest.strip()]))
                else:
                    clusters.append((cp, []))
            else:
                clusters[-1][1].append(line.strip())
        # text version of glyphs
        # a glyph is any key/value where the value contains no alphanumerics
        glyphs = {
            _cluster[0]: _cluster[1]
            for _cluster in clusters
            if not set(''.join(_cluster[1])) & set(string.digits + string.ascii_letters)
        }
        # properties: anything that does contain alphanumerics
        properties = {
            _cluster[0]: ' '.join(_cluster[1])
            for _cluster in clusters
            if set(''.join(_cluster[1])) & set(string.digits + string.ascii_letters)
        }
        # convert to bitlist
        glyphs = {
            _key: Glyph(tuple(tuple(_c not in back for _c in _row) for _row in _value))
            for _key, _value in glyphs.items()
        }

        def _toint(key):
            try:
                return int(key, 16)
            except ValueError:
                return key

        glyphs = {_toint(_key): _value for _key, _value in glyphs.items()}
        return Font(glyphs, comments, properties)


@Font.saves('text', 'txt', 'draw', 'yaff')
def save(font, outfile, fore='@', back='.', comment='#'):
    """Write font to a plaintext file."""
    with ensure_stream(outfile, 'w') as outstream:
        if font._comments:
            for line in font._comments:
                outstream.write('{} {}\n'.format(comment, line))
            outstream.write('\n')
        if font._properties:
            for key in PROPERTIES:
                try:
                    value = font._properties.pop(key)
                    outstream.write('{}: {}\n'.format(key, value))
                except KeyError:
                    pass
            for key, value in font._properties.items():
                outstream.write('{}: {}\n'.format(key, value))
            outstream.write('\n')
        for ordinal, char in font._glyphs.items():
            char = [''.join((fore if _b else back) for _b in _row) for _row in char._rows]
            if isinstance(ordinal, int):
                outstream.write('{:02x}:\n\t'.format(ordinal))
            else:
                outstream.write('{}:\n\t'.format(ordinal))
            outstream.write('\n\t'.join(char))
            outstream.write('\n\n')
    return font
