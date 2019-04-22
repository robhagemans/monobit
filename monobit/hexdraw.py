"""
monobit.hexdraw - read and write .draw files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .base import ensure_stream, Font


_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters

# default background characters
_BACK = "_.-`'0"
# for now, anything else is foreground
#_FORE = '@#*1'


@Font.loads('txt')
@Font.loads('draw')
@Font.loads('yaff')
def load(infile, back=_BACK):
    """Read a hexdraw plaintext font file."""
    with ensure_stream(infile, 'r') as instream:
        lines = list(instream)
        comments = [
            _line[1:].rstrip('\r\n')
            for _line in lines
            if _line.rstrip('\r\n') and _line[0] not in _CODESTART
        ]
        # drop all comments
        codelines = (
            _line
            for _line in lines
            if _line and _line[0] in _CODESTART
        )
        # cluster by character
        # assuming only one code point per glyph, for now
        clusters = []
        for line in codelines:
            if line[0] in string.hexdigits:
                cp, rest = line.strip().split(':')
                if rest:
                    clusters.append((cp, [rest.strip()]))
                else:
                    clusters.append((cp, []))
            else:
                clusters[-1][1].append(line.strip())
        # text version of glyphs
        glyphs = {
            int(_cluster[0], 16): _cluster[1]
            for _cluster in clusters
        }
        # convert to bitlist
        glyphs = {
            _key: [[_c not in back for _c in _row] for _row in _value]
            for _key, _value in glyphs.items()
        }
        return Font(glyphs, comments)


@Font.saves('txt')
@Font.saves('draw')
@Font.saves('yaff')
def save(font, outfile, fore='@', back='.', comment='#'):
    """Write font to hexdraw file."""
    with ensure_stream(outfile, 'w') as outstream:
        for line in font._comments:
            outstream.write('{}{}\n'.format(comment, line))
        if font._comments:
            outstream.write('\n')
        for ordinal, char in font._glyphs.items():
            char = [''.join((fore if _b else back) for _b in _row) for _row in char]
            outstream.write('{:02x}:\n\t'.format(ordinal))
            outstream.write('\n\t'.join(char))
            outstream.write('\n\n')
