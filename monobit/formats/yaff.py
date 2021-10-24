"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from types import SimpleNamespace
from itertools import count

from ..matrix import to_text
from ..storage import loaders, savers
from ..encoding import charmaps
from ..streams import FileFormatError
from ..font import PROPERTIES, Font
from ..glyph import Glyph
from ..label import strip_matching, label as to_label
from ..label import Char, Codepoint, Tag


##############################################################################
# format parameters

_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters + '_-."'

BOUNDARY_MARKER = '---'

def _parse_yaff_keys(keys):
    """Convert keys on input from .yaff."""
    kwargs = dict(
        char='',
        codepoint=(),
        tags=[],
    )
    for key in keys:
        label = to_label(key)
        indexer = label.indexer()
        try:
            kwargs['tags'].append(indexer['tag'])
            continue
        except KeyError:
            pass
        kwargs.update(indexer)
    return kwargs

def _parse_draw_keys(keys):
    """Convert keys on input from .draw."""
    kwargs = dict(
        char='',
        codepoint=(),
        tags=(),
    )
    # only one key allowed in .draw, rest ignored
    key = keys[0]
    try:
        kwargs['char'] = chr(int(key, 16))
    except (TypeError, ValueError):
        kwargs['tags'] = [key]
    return kwargs


_YAFF_PARAMETERS = dict(
    ink='@',
    paper='.',
    comment='#',
    tab='    ',
    separator=':',
    empty='-',
    parse_glyph_keys=_parse_yaff_keys
)

_DRAW_PARAMETERS = dict(
    comment='%',
    tab='\t',
    separator=':',
    empty='-',
    parse_glyph_keys=_parse_draw_keys
)

##############################################################################


@loaders.register('yaff', 'yaffs', magic=(b'---',), name='monobit-yaff')
def load_yaff(instream, where=None):
    """Load font from a monobit .yaff file."""
    return _load_fonts(instream.text, **_YAFF_PARAMETERS)

@savers.register(linked=load_yaff)
def save(fonts, outstream, where=None):
    """Write fonts to a monobit .yaff file."""
    _save_yaff(fonts, outstream.text, **_YAFF_PARAMETERS)


@loaders.register('draw', 'text', 'txt', name='hexdraw')
def load_draw(instream, where=None, ink='#', paper='-'):
    """
    Load font from a hexdraw file.

    ink: character used for inked/foreground pixels
    paper: character used for uninked/background pixels
    """
    params = dict(ink=ink, paper=paper, **_DRAW_PARAMETERS)
    return _load_fonts(instream.text, **params)

@savers.register(linked=load_draw)
def save_draw(fonts, outstream, where=None, ink='#', paper='-'):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels
    paper: character to use for uninked/background pixels
    """
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    params = dict(ink=ink, paper=paper, **_DRAW_PARAMETERS)
    _save_draw(fonts[0], outstream.text, **params)


##############################################################################
# handle comments (used by hex)

def clean_comment(comment):
    """Remove leading characters from comment."""
    while comment and not comment[-1]:
        comment = comment[:-1]
    if not comment:
        return []
    comment = [(_line if _line else '') for _line in comment]
    # remove "comment char" - non-alphanumeric shared first character
    firsts = [_line[0:1] for _line in comment if _line]
    if len(set(firsts)) == 1 and firsts[0] not in string.ascii_letters + string.digits:
        comment = [_line[1:] for _line in comment]
    # normalise leading whitespace
    if all(_line.startswith(' ') for _line in comment if _line):
        comment = [_line[1:] for _line in comment]
    return comment

def split_global_comment(comment):
    while comment and not comment[-1]:
        comment = comment[:-1]
    try:
        splitter = comment[::-1].index('')
    except ValueError:
        global_comment = comment
        comment = []
    else:
        global_comment = comment[:-splitter-1]
        comment = comment[-splitter:]
    return global_comment, comment

def write_comments(outstream, comments, comm_char, is_global=False):
    """Write out the comments attached to a given font item."""
    if comments:
        if not is_global:
            outstream.write('\n')
        for line in comments:
            outstream.write('{} {}\n'.format(comm_char, line))
        if is_global:
            outstream.write('\n')


##############################################################################
# read file

def _new_cluster():
    """Bag of elements clustered in a text file (glyph, property, etc)."""
    return SimpleNamespace(
        keys=[],
        values=[],
        comments=[]
    )

def _load_fonts(instream, ink, paper, separator, empty, parse_glyph_keys, **kwargs):
    """Read and parse a plaintext font file."""
    pack = []
    for number in count():
        elements, eof = _read_text(instream, separator)
        if eof and not elements:
            break
        if not elements:
            logging.debug('Section #%d is empty.', number)
            # no font to read, no comments to keep
            continue
        logging.debug('Found content in section #%d.', number)
        # extract comments
        elements, global_comments = _extract_comments(elements)
        # first take out all glyphs
        glyphs = _parse_glyphs(elements, ink, paper, empty, parse_glyph_keys)
        # property comments currently not preserved
        properties, property_comments = _parse_properties(elements, ink, paper)
        comments = {'': global_comments, **property_comments}
        # construct font
        pack.append(Font(glyphs, comments, properties))
    return pack

def _read_text(instream, separator):
    """Read a plaintext font file."""
    # cluster by property/character/comment block
    elements = []
    current = _new_cluster()
    parsing_comment = False
    eof = False
    for line in instream:
        if line.strip() == BOUNDARY_MARKER:
            break
        # strip all trailing whitespace (important!)
        line = line.rstrip()
        if not line:
            # preserve empty lines if they separate comments
            if parsing_comment:
                current.comments.append('')
        elif current.keys and line[0] in _WHITESPACE:
            # found a follow-up value line
            current.values.append(line.lstrip())
        else:
            # found a key or comment
            if current.values:
                # we already have values for the last key, so this is a new cluster
                elements.append(current)
                current = _new_cluster()
            parsing_comment = line[0] not in _CODESTART
            if parsing_comment:
                current.comments.append(line)
            else:
                key, sep, rest = line.partition(separator)
                if sep != separator:
                    raise ValueError(
                        'Invalid .yaff or .draw file: '
                        f'key `{key.strip()}` not followed by `{separator}`'
                    )
                current.keys.append(key)
                # remainder of label line after : is first value line
                if rest:
                    current.values.append(rest.lstrip())
    else:
        # we're run through the whole file, no separators
        eof = True
    # append any trailing content
    if current.keys or current.values or current.comments:
        elements.append(current)
    return elements, eof


def _is_glyph(value, ink, paper):
    """Text line is a glyph."""
    return not(set(value) - set(ink) - set(paper))

def _parse_properties(elements, ink, paper):
    """Parse properties."""
    # properties: anything that contains more than .@
    property_elements = [
        _el for _el in elements
        if not any(_is_glyph(_line, ink, paper) for _line in _el.values)
    ]
    # multiple labels translate into multiple keys with the same value
    properties = {
        # strip matching double quotes on a per-line basis
        _key: '\n'.join(strip_matching(_line, '"') for _line in _el.values)
        for _el in property_elements
        for _key in _el.keys
    }
    # property comments
    comments = {
        _key: clean_comment(_el.comments)
        for _el in property_elements
        for _key in _el.keys
    }
    return properties, comments

def _parse_glyphs(elements, ink, paper, empty, parse_glyph_keys):
    """Parse glyphs."""
    # text version of glyphs
    # a glyph is any key/value where at least one line in the value contains no alphanumerics
    # to avoid detection as glyph, a value can be quited
    glyph_elements = [
        _el for _el in elements
        if any(_is_glyph(_line, ink, paper) for _line in _el.values)
    ]
    # convert text representation to glyph
    glyphs = [
        _parse_glyph(_el, ink, paper, empty, parse_glyph_keys)
        for _el in glyph_elements
    ]
    return glyphs

def _parse_glyph(element, ink, paper, empty, parse_glyph_keys):
    """Parse single glyph."""
    glyph_lines = [_line for _line in element.values if _is_glyph(_line, ink, paper)]
    if glyph_lines == [empty]:
        glyph = Glyph()
    else:
        glyph = Glyph.from_matrix(glyph_lines, paper=paper)
    # glyph properties
    prop_lines =  [_line for _line in element.values if not _is_glyph(_line, ink, paper)]
    # FIXME - this is hacky
    # we're submitting prop_lines as instream becuase for line in will work
    # some kind of recursive call makes sense though
    elements, _ = _read_text(prop_lines, separator=':')
    if elements:
        # ignore in-glyph comments
        props, _ = _parse_properties(elements, ink, paper)
        glyph = glyph.modify(**props)
    glyph = glyph.set_annotations(
        comments=clean_comment(element.comments),
        **parse_glyph_keys(element.keys)
    )
    return glyph

def _extract_comments(elements):
    """Parse comments and remove from element list."""
    if not elements:
        return []
    # header comment
    if elements[0].keys:
        # split out global comment
        header_comment, elements[0].comments = split_global_comment(elements[0].comments)
        elements[0].comments = clean_comment(elements[0].comments)
        header_comment = clean_comment(header_comment)
    else:
        header_comment = elements[0].comments
        elements = elements[1:]
    comments = clean_comment(header_comment)
    # preserve any comment at end of file
    if elements and not elements[-1].keys:
        elements[-1].comments = clean_comment(elements[-1].comments)
        # separate header and footer with empty line
        if comments and elements[-1].comments:
            comments.append('')
        comments.extend(clean_comment(elements[-1].comments))
        elements = elements[:-1]
    return elements, comments


##############################################################################
# write file

def _write_glyph(outstream, labels, glyph, ink, paper, comm_char, tab, separator, empty):
    """Write out a single glyph in text format."""
    if not labels:
        logging.warning('No labels for glyph: %s', glyph)
        return
    write_comments(outstream, glyph.comments, comm_char=comm_char)
    for _label in labels:
        outstream.write(str(_label) + separator)
    glyphtxt = to_text(glyph.as_matrix(), ink=ink, paper=paper, line_break='\n'+tab)
    # empty glyphs are stored as 0x0, not 0xm or nx0
    if not glyph.width or not glyph.height:
        glyphtxt = empty
    outstream.write(tab + glyphtxt + '\n')
    if glyph.offset:
        outstream.write(f'\n{tab}offset: {str(glyph.offset)}')
    if glyph.tracking:
        outstream.write(f'\n{tab}tracking: {str(glyph.tracking)}')
    if glyph.offset or glyph.tracking:
        outstream.write('\n')
    outstream.write('\n\n')

def _quote_if_needed(value):
    """See if string value needs double quotes."""
    if (
            (value.startswith('"') and value.endswith('"'))
            or value[:1].isspace() or value[-1:].isspace()
        ):
        return f'"{value}"'
    return value

def _write_prop(outstream, key, value, tab, comments, comm_char):
    """Write out a property."""
    if value is None:
        return
    # this may use custom string converter (e.g codepoint labels)
    value = str(value)
    if not value:
        return
    write_comments(outstream, comments, comm_char=comm_char)
    if '\n' not in value:
        outstream.write(f'{key}: {_quote_if_needed(value)}\n')
    else:
        outstream.write(
            ('{}:\n' + tab + '{}\n').format(
                key, ('\n' + tab).join(_quote_if_needed(_line) for _line in value.splitlines())
            )
        )

def _save_yaff(fonts, outstream, ink, paper, comment, tab, separator, empty, **kwargs):
    """Write one font to a plaintext stream."""
    for number, font in enumerate(fonts):
        if len(fonts) > 1:
            outstream.write(BOUNDARY_MARKER + '\n')
        logging.debug('Writing %s to section #%d', font.name, number)
        write_comments(outstream, font.get_comments(), comm_char=comment, is_global=True)
        # we always output name, font-size and spacing
        # plus anything that is different from the default
        props = {
            'name': font.name,
            'spacing': font.spacing,
            **font.nondefault_properties
        }
        if font.spacing in ('character-cell', 'multi-cell'):
            props['raster-size'] = font.raster_size
        else:
            props['bounding-box'] = font.bounding_box
        if props:
            # write recognised yaff properties first, in defined order
            for key in PROPERTIES:
                value = props.pop(key, '')
                comments = font.get_comments(key)
                _write_prop(outstream, key, value, tab, comments=comments, comm_char=comment)
            # write out any remaining properties
            for key, value in props.items():
                comments = font.get_comments(key)
                _write_prop(outstream, key, value, tab, comments=comments, comm_char=comment)
            outstream.write('\n')
        for glyph in font.glyphs:
            labels = []
            # don't write out codepoints for unicode fonts as we have u+XXXX already
            if glyph.codepoint and (not charmaps.is_unicode(font.encoding) or not glyph.char):
                labels.append(Codepoint(glyph.codepoint))
            if glyph.char:
                labels.append(Char(glyph.char))
            labels.extend(Tag(_tag) for _tag in glyph.tags)
            _write_glyph(
                outstream, labels,
                glyph, ink, paper, comment, tab, separator + '\n', empty
            )

def _save_draw(font, outstream, ink, paper, comment, tab, separator, empty, **kwargs):
    """Write one font to a plaintext stream."""
    write_comments(outstream, font.get_comments(), comm_char=comment, is_global=True)
    for glyph in font.glyphs:
        if len(glyph.char) > 1:
            logging.warning(
                "Can't encode grapheme cluster %s in .draw file; skipping.",
                Char(glyph.char)
            )
            continue
        label = f'{ord(glyph.char):04x}'
        _write_glyph(
            outstream, [label],
            glyph, ink, paper, comment, tab, separator, empty
        )
