"""
monobit.text - read and write yaff and hexdraw files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
from types import SimpleNamespace

from .base import (
    Typeface, Font, Glyph, clean_comment, write_comments, split_global_comment
)


_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters + '_'

# default background characters
_ACCEPTED_BACK = "_.-"
# for now, anything else is foreground
#_ACEPTED_FORE = '@#*'

_SEPARATOR = '---'


def yaff_input_key(key):
    """Convert keys on input from .yaff."""
    try:
        return int(key, 0)
    except (TypeError, ValueError):
        try:
            # accept decimals with leading zeros
            return int(key.lstrip('0'))
        except (TypeError, ValueError, AttributeError):
            return key

def yaff_output_key(key):
    """Convert keys for output to .yaff"""
    if isinstance(key, int):
        return '0x{:02x}'.format(key)
    else:
        return str(key)


def draw_input_key(key):
    """Convert keys on input from .draw."""
    try:
        return int(key, 16)
    except (TypeError, ValueError):
        return key

def draw_output_key(key):
    """Convert keys on input from .draw."""
    try:
        return '{:04x}'.format(key)
    except ValueError:
        raise ValueError('.draw format only supports integer keys')



# defaults
yaff_parameters = {
    'fore': '@',
    'back': '.',
    'comment': '#',
    'tab': '    ',
    'key_format': yaff_output_key,
    'key_sep': ':\n'
}
draw_parameters = {
    'fore': '#',
    'back': '-',
    'comment': '%',
    'tab': '\t',
    'key_format': draw_output_key,
    'key_sep': ':'
}


# default order of known yaff properties
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
    'x-width', # width of lowercase x (in proportional font)

    # positioning relative to origin:
    'direction', # left-to-right, right-to-left
    'bottom', # bottom line of matrix relative to baseline
    'offset-before', # horizontal offset from origin to matrix start
    'offset-after', # horizontal offset from matrix end to next origin

    # other metrics (may affect interline spacing):
    'size', # pixel height == top - bottom (can be 'width height' for fixed-width)
    'ascent', # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent', # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'leading', # vertical leading, defined as (pixels between baselines) - (pixel height)
    'x-height', # height of lowercase x relative to baseline
    'cap-height', # height of capital relative to baseline

    # character set:
    'encoding',
    'default-char',
    'space-char',

    # conversion metadata:
    'converter',
    'source-name',
    'source-format',
]


@Typeface.loads('text', 'txt', 'yaff', encoding='utf-8-sig')
def load(instream):
    """Read a plaintext font file."""
    fonts = []
    while True:
        font = _load_font(instream, back=_ACCEPTED_BACK, key_format=yaff_input_key)
        if font is None:
            break
        fonts.append(font)
    if fonts:
        return Typeface(fonts)
    raise ValueError('No fonts found in file.')

@Typeface.saves('text', 'txt', 'yaff', encoding='utf-8')
def save(typeface, outstream):
    """Write fonts to a yaff file."""
    for i, font in enumerate(typeface._fonts):
        if i:
            outstream.write(_SEPARATOR + '\n')
        _save_font(font, outstream, **yaff_parameters)
    return typeface


@Typeface.loads('draw', encoding='utf-8-sig')
def load_draw(instream):
    """Read a hexdraw font file."""
    fonts = [_load_font(instream, back=_ACCEPTED_BACK, key_format=draw_input_key)]
    return Typeface(fonts)

@Typeface.saves('draw', encoding='utf-8')
def save_draw(typeface, outstream):
    """Write font to a hexdraw file."""
    if len(typeface._fonts) > 1:
        raise ValueError('Saving multiple fonts to .draw not possible')
    font = typeface._fonts[0]
    _save_font(font, outstream, **draw_parameters)
    return typeface


##############################################################################
# read file

class Cluster(SimpleNamespace):
    """Bag of elements relating to one glyph."""

def new_cluster(**kwargs):
    return Cluster(
        labels=[],
        clusters=[],
        comments=[]
    )

def _load_font(instream, back, key_format):
    """Read a plaintext font file."""
    global_comment = []
    current_comment = []
    # cluster by character
    elements = []
    for line in instream:
        if not line.rstrip('\r\n'):
            # preserve empty lines if they separate comments
            if current_comment and current_comment[-1] != '':
                current_comment.append('')
        elif line.startswith(_SEPARATOR):
            # stream separator, end of Font
            break
        elif line[0] not in _CODESTART:
            current_comment.append(line.rstrip('\r\n'))
        elif line[0] not in _WHITESPACE:
            # split out global comment
            if not elements:
                elements.append(new_cluster())
                if current_comment:
                    global_comm, current_comment = split_global_comment(current_comment)
                    global_comment.extend(global_comm)
            label, rest = line.strip().split(':', 1)
            if elements[-1].clusters:
                # we already have stuff for the last key, so this is a new one
                elements.append(new_cluster())
            elements[-1].comments.extend(clean_comment(current_comment))
            current_comment = []
            elements[-1].labels.append(label)
            # remainder of label line after : is glyph row or property value
            rest = rest.strip()
            if rest:
                elements[-1].clusters.append(rest)
        else:
            elements[-1].clusters.append(line.strip())
    if not elements and not global_comment:
        # no font to read, no comments to keep
        return None
    # preserve any comment at end of file
    current_comment = clean_comment(current_comment)
    if current_comment:
        elements.append(new_cluster())
        elements[-1].comments = current_comment
    # properties: anything that contains alphanumerics
    property_elements = [
        _el for _el in elements
        if set(''.join(_el.clusters)) & set(string.digits + string.ascii_letters)
    ]
    # multiple labels translate into multiple keys with the same value
    properties = {
        _key: ''.join(_el.clusters)
        for _el in property_elements
        for _key in _el.labels
    }
    # text version of glyphs
    # a glyph is any key/value where the value contains no alphanumerics
    glyph_elements = [
        _el for _el in elements
        if not set(''.join(_el.clusters)) & set(string.digits + string.ascii_letters)
    ]
    labels = {
        key_format(_lab): _index
        for _index, _el in enumerate(glyph_elements)
        for _lab in _el.labels
    }
    # convert text representation to glyph
    glyphs = [
        Glyph.from_text(_el.clusters, background=back).add_comments(_el.comments)
        for _el in glyph_elements
    ]
    # extract property comments
    comments = {
        key_format(_key): _el.comments
        for _el in property_elements
        for _key in _el.labels
    }
    comments[None] = clean_comment(global_comment)
    return Font(glyphs, labels, comments, properties)


##############################################################################
# write file

def _save_font(font, outstream, fore, back, comment, tab, key_format, key_sep):
    """Write one font to a plaintext stream."""
    write_comments(outstream, font._comments.get(None, []), comm_char=comment, is_global=True)
    if font._properties:
        for key in PROPERTIES:
            write_comments(outstream, font._comments.get(key, []), comm_char=comment)
            try:
                value = font._properties.pop(key)
                if value not in ('', None):
                    outstream.write('{}: {}\n'.format(key, value))
            except KeyError:
                pass
        for key, value in font._properties.items():
            write_comments(outstream, font._comments.get(key, []), comm_char=comment)
            if value not in ('', None):
                outstream.write('{}: {}\n'.format(key, value))
        outstream.write('\n')
    for labels, char in font:
        write_comments(outstream, char.comments, comm_char=comment)
        for ordinal in labels:
            outstream.write(key_format(ordinal) + key_sep)
        outstream.write(tab)
        outstream.write(('\n' + tab).join(char.as_text(foreground=fore, background=back)))
        outstream.write('\n\n')
