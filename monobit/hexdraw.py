"""
monobit.hexdraw - read and write .draw files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .base import ensure_stream

# TODO: preserve comments, maybe metadata


def load(infile, back='-'):
    """Read a hexdraw plaintext font file."""
    with ensure_stream(infile, 'r') as instream:
        # drop all comments
        codelines = (
            _line
            for _line in instream.readlines()
            if _line and _line[0] in ' \t' + string.hexdigits
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
            _key: [[_c != back for _c in _row] for _row in _value]
            for _key, _value in glyphs.items()
        }
        return glyphs


def save(font, outfile, fore='#', back='-'):
    """Write font to hexdraw file."""
    with ensure_stream(outfile, 'w') as outstream:
        for ordinal, char in font.items():
            char = [''.join((fore if _b else back) for _b in _row) for _row in char]
            outstream.write('{:02x}:\n\t'.format(ordinal))
            outstream.write('\n\t'.join(char))
            outstream.write('\n\n')
