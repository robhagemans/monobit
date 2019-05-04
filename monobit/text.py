"""
monobit.text - read and write hexdraw and yaff files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .base import ensure_stream, Typeface, Font, Glyph


_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters

# default background characters
_BACK = "_.-"
# for now, anything else is foreground
#_FORE = '@#*'

# default order of known properties
PROPERTIES = [

    # font metadata:
    'name', # full human name
    'foundry', # author or issuer
    'copyright', # copyright string
    'notice', # e.g. license string
    'revision', # font version

    # descriptive:
    'points', # nominal point size
    'dpi', # target resolution in dots per inch
    'family', # typeface/font family
    'weight', # normal, bold, light, etc.
    'slant', # roman, italic, oblique, etc
    'setwidth', # normal, condensed, expanded, etc.
    'style', # serif, sans, etc.
    'decoration', # underline, strikethrough, etc.
    'spacing', # proportional, monospace, cell

    # positioning relative to origin:
    'direction', # left-to-right, right-to-left
    'bottom', # bottom line of matrix relative to baseline
    'offset-before', # horizontal offset from origin to matrix start
    'offset-after', # horizontal offset from matrix end to next origin

    # other metrics (may affect interline spacing):
    'size', # pixel height == top - bottom
    'ascent', # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent', # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'x-height', # height of lowercase x relative to baseline
    'cap-height', # height of capital relative to baseline

    # character set:
    'encoding',
    'default-char',

    # conversion metadata:
    'converter',
    'source-name',
    'source-format',
]


@Typeface.loads('text', 'txt', 'draw', 'yaff')
def load(infile, back=_BACK):
    """Read a plaintext font file."""
    with ensure_stream(infile, 'r', encoding='utf-8-sig') as instream:
        lines = list(instream)
        comments = {None: []}
        current_comment = []
        # cluster by character
        # assuming only one code point per glyph, for now
        clusters = []
        cp = None
        for line in lines:
            if not line.rstrip('\r\n'):
                # preserve empty lines if they separate comments
                if current_comment and current_comment[-1] != '':
                    current_comment.append(None)
            elif line[0] not in _CODESTART:
                current_comment.append(line[1:].rstrip('\r\n'))
            elif line[0] not in _WHITESPACE:
                while current_comment and not current_comment[-1]:
                    current_comment = current_comment[:-1]
                # split out global comment
                if cp is None and current_comment:
                    try:
                        splitter = current_comment[::-1].index(None)
                    except ValueError:
                        comments[None] = current_comment
                        current_comment = []
                    else:
                        comments[None] = current_comment[:-splitter-1]
                        current_comment = current_comment[-splitter:]
                cp, rest = line.strip().split(':', 1)
                current = cp
                comments[cp] = current_comment
                current_comment = []
                if rest:
                    clusters.append((cp, [rest.strip()]))
                else:
                    clusters.append((cp, []))
            else:
                clusters[-1][1].append(line.strip())
        comments[cp].extend(current_comment)
        # normalise comment spacing
        for key in comments:
            comments[key] = [(_line if _line else '') for _line in comments[key]]
            if all(_line.startswith(' ') for _line in comments[key] if _line):
                comments[key] = [_line[1:] for _line in comments[key]]
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
            except (TypeError, ValueError):
                return key

        glyphs = {_toint(_key): _value for _key, _value in glyphs.items()}
        comments = {_toint(_key): _value for _key, _value in comments.items()}
        return Typeface([Font(glyphs, comments, properties)])


def _write_comments(outstream, comments, key, comm_char='#'):
    if comments and key in comments and comments[key]:
        if key is not None:
            outstream.write('\n')
        for line in comments[key]:
            outstream.write('{} {}\n'.format(comm_char, line))
        if key is None:
            outstream.write('\n')

@Typeface.saves('text', 'txt', 'draw', 'yaff')
def save(typeface, outfile, fore='@', back='.', comment='#'):
    """Write font to a plaintext file."""
    with ensure_stream(outfile, 'w') as outstream:
        for i, font in enumerate(typeface._fonts):
            if i > 0:
                outstream.write('---\n\n')
            _write_comments(outstream, font._comments, None, comm_char=comment)
            if font._properties:
                for key in PROPERTIES:
                    _write_comments(outstream, font._comments, key, comm_char=comment)
                    try:
                        value = font._properties.pop(key)
                        if value:
                            outstream.write('{}: {}\n'.format(key, value))
                    except KeyError:
                        pass
                for key, value in font._properties.items():
                    _write_comments(outstream, font._comments, key, comm_char=comment)
                    if value:
                        outstream.write('{}: {}\n'.format(key, value))
                outstream.write('\n')
            for ordinal, char in font._glyphs.items():
                _write_comments(outstream, font._comments, ordinal, comm_char=comment)
                char = [''.join((fore if _b else back) for _b in _row) for _row in char._rows]
                if isinstance(ordinal, int):
                    outstream.write('{:02x}:\n\t'.format(ordinal))
                else:
                    outstream.write('{}:\n\t'.format(ordinal))
                outstream.write('\n\t'.join(char))
                outstream.write('\n\n')
    return typeface
