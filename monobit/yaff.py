"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from types import SimpleNamespace

from .text import clean_comment, write_comments, split_global_comment, to_text
from .formats import Loaders, Savers
from .font import PROPERTIES, Font
from .glyph import Glyph
from .label import label as to_label
from .label import UnicodeLabel, TagLabel, CodepointLabel


_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters + '_'



# defaults
_YAFF_PARAMETERS = dict(
    fore='@',
    back='.',
    comment='#',
    tab='    ',
    key_sep=':\n',
    empty='-',
)

_DRAW_PARAMETERS = dict(
    fore='#',
    back='-',
    comment='%',
    tab='\t',
    key_sep=':',
    empty='-',
)


def _parse_yaff_keys(keys):
    """Convert keys on input from .yaff."""
    kwargs = dict(
        char='',
        codepoint=None,
        tags=[],
    )
    for key in keys:
        label = to_label(key)
        if isinstance(label, TagLabel):
            kwargs['tags'].append(str(label))
        elif isinstance(label, CodepointLabel):
            # TODO: multi-codepoint labels
            kwargs['codepoint'] = int(label)
        else:
            kwargs['char'] = label.to_char()
    return kwargs

def _parse_draw_keys(keys):
    """Convert keys on input from .draw."""
    kwargs = dict(
        char='',
        codepoint=None,
        tags=[],
    )
    # only one key allowed in .draw, rest ignored
    key = keys[0]
    try:
        kwargs['char'] = chr(int(key, 16))
    except (TypeError, ValueError):
        kwargs['tags'] = [key]
    return kwargs



@Loaders.register('yaff', 'text', 'txt', name='monobit-yaff')
def load(instream):
    """Read a plaintext font file."""
    font = _load_font(instream, fore='@', back='.', parse_glyph_keys=_parse_yaff_keys)
    if font is None:
        raise ValueError('No fonts found in file.')
    return font

@Savers.register('yaff', 'text', 'txt', multi=False)
def save(font, outstream):
    """Write fonts to a yaff file."""
    _save_yaff(font, outstream, **_YAFF_PARAMETERS)
    return font


@Loaders.register('draw', name='hexdraw')
def load_draw(instream):
    """Read a hexdraw font file."""
    font = _load_font(instream, fore='#', back='-', parse_glyph_keys=_parse_draw_keys)
    if font is None:
        raise ValueError('No fonts found in file.')
    return font

@Savers.register('draw', multi=False)
def save_draw(font, outstream):
    """Write font to a hexdraw file."""
    _save_draw(font, outstream, **_DRAW_PARAMETERS)
    return font


##############################################################################
# read file

class Cluster(SimpleNamespace):
    """Bag of elements clustered in a text file (glyph, property, etc)."""


def new_cluster(**kwargs):
    return Cluster(
        keys=[],
        values=[],
        comments=[]
    )

def _load_font(instream, fore, back, parse_glyph_keys):
    """Read and parse a plaintext font file."""
    header_comment, elements, footer_comment = _read_text(instream)
    if not elements and not header_comment:
        # no font to read, no comments to keep
        return None
    # property comments currently not preserved
    properties, property_comments = _parse_properties(elements, fore, back)
    glyphs = _parse_glyphs(elements, fore, back, parse_glyph_keys)
    # parse comments
    # global comment
    comments = clean_comment(header_comment)
    # preserve any comment at end of file
    comments.extend(clean_comment(footer_comment))
    # construct font
    return Font(glyphs, comments, properties)


def _read_text(instream):
    """Read a plaintext font file."""
    header_comment = []
    current_comment = []
    # cluster by property/character/comment block
    elements = []
    for line in instream:
        if not line.rstrip('\r\n'):
            # preserve empty lines if they separate comments
            if current_comment and current_comment[-1] != '':
                current_comment.append('')
        elif line[0] not in _CODESTART:
            current_comment.append(line.rstrip('\r\n'))
        elif line[0] not in _WHITESPACE:
            # split out global comment
            if not elements:
                elements.append(new_cluster())
                if current_comment:
                    global_comm, current_comment = split_global_comment(current_comment)
                    header_comment.extend(global_comm)
            label, sep, rest = line.partition(':')
            if sep != ':':
                raise ValueError(
                    f'Invalid .yaff or .draw file: key `{label.strip()}` not followed by `:`'
                )
            if elements[-1].values:
                # we already have stuff for the last key, so this is a new one
                elements.append(new_cluster())
            elements[-1].comments.extend(clean_comment(current_comment))
            current_comment = []
            elements[-1].keys.append(label)
            # remainder of label line after : is glyph row or property value
            rest = rest.strip()
            if rest:
                elements[-1].values.append(rest)
        else:
            elements[-1].values.append(line.strip())
    return header_comment, elements, current_comment


def _is_glyph(value, fore, back):
    """Value is a glyph."""
    return not(set(value) - set(fore) - set(back))

def _parse_properties(elements, fore, back):
    """Parse properties."""
    # properties: anything that contains more than .@
    property_elements = [
        _el for _el in elements
        if not _is_glyph(''.join(_el.values), fore, back)
    ]
    # multiple labels translate into multiple keys with the same value
    properties = {
        _key: '\n'.join(_el.values)
        for _el in property_elements
        for _key in _el.keys
    }
    # property comments
    comments = {
        _key: _el.comments
        for _el in property_elements
        for _key in _el.keys
    }
    return properties, comments


def _parse_glyphs(elements, fore, back, parse_glyph_keys):
    # parse glyphs
    # text version of glyphs
    # a glyph is any key/value where the value contains no alphanumerics
    glyph_elements = [
        _el for _el in elements
        if _is_glyph(''.join(_el.values), fore, back)
    ]
    # convert text representation to glyph
    glyphs = [
        (
            (
                Glyph.from_matrix(_el.values, background=back)
                if _el.values != ['-']
                else Glyph.empty()
            ).set_annotations(
                comments=_el.comments,
                **parse_glyph_keys(_el.keys)
            )
        )
        for _el in glyph_elements
    ]
    return glyphs



##############################################################################
# write file

def _write_glyph(outstream, labels, glyph, fore, back, comm_char, tab, key_sep, empty):
    """Write out a single glyph in text format."""
    if not labels:
        logging.warning('No labels for glyph: %s', glyph)
        return
    write_comments(outstream, glyph.comments, comm_char=comm_char)
    for _label in labels:
        outstream.write(_label + key_sep)
    glyphtxt = to_text(glyph.as_matrix(fore, back), line_break='\n'+tab)
    # empty glyphs are stored as 0x0, not 0xm or nx0
    if not glyph.width or not glyph.height:
        glyphtxt = empty
    outstream.write(tab)
    outstream.write(glyphtxt)
    outstream.write('\n\n')

def _write_prop(outstream, key, value, tab):
    """Write out a property."""
    if value is None:
        return
    # this may use custom string converter (e.g codepoint labels)
    value = str(value)
    if not value:
        return
    if '\n' not in value:
        outstream.write('{}: {}\n'.format(key, value))
    else:
        outstream.write(
            ('{}:\n' + tab + '{}\n').format(
                key, ('\n' + tab).join(value.splitlines())
            )
        )

def _save_yaff(font, outstream, fore, back, comment, tab, key_sep, empty):
    """Write one font to a plaintext stream."""
    write_comments(outstream, font.get_comments(), comm_char=comment, is_global=True)
    # we always output name, font-size and spacing
    # plus anything that is different from the default
    props = {
        'name': font.name,
        'point-size': font.point_size,
        'spacing': font.spacing,
        **font.nondefault_properties
    }
    if props:
        # write recognised yaff properties first, in defined order
        for key in PROPERTIES:
            value = props.pop(key, '')
            _write_prop(outstream, key, value, tab)
        # write out any remaining properties
        for key, value in props.items():
            _write_prop(outstream, key, value, tab)
        outstream.write('\n')
    for glyph in font.glyphs:
        labels = []
        if glyph.codepoint is not None:
            labels.append(repr(CodepointLabel(glyph.codepoint)))
        if glyph.char:
            labels.append(repr(UnicodeLabel.from_char(glyph.char)))
        labels.extend(glyph.tags)
        _write_glyph(
            outstream, labels,
            glyph, fore, back, comment, tab, key_sep, empty
        )

def _save_draw(font, outstream, fore, back, comment, tab, key_sep, empty):
    """Write one font to a plaintext stream."""
    write_comments(outstream, font.get_comments(), comm_char=comment, is_global=True)
    for glyph in font.glyphs:
        if len(glyph.char) > 1:
            logging.warning(
                "Can't encode grapheme cluster %s in .draw file; skipping.",
                UnicodeLabel.from_char(glyph.char)
            )
            continue
        label = f'{ord(glyph.char):04x}'
        _write_glyph(
            outstream, [label],
            glyph, fore, back, comment, tab, key_sep, empty
        )
