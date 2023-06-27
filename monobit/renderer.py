"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from unicodedata import bidirectional, normalize, category

try:
    from bidi.algorithm import get_display, get_base_level
except ImportError:
    def _bidi_not_found(*args, **kwargs):
        raise ImportError(
            'Bidirectional text requires module `python-bidi`; not found.'
        )
    get_display = _bidi_not_found
    get_base_level = _bidi_not_found

try:
    from arabic_reshaper import reshape
except ImportError:
    def reshape(text):
        raise ImportError(
            'Arabic text requires module `arabic-reshaper`; not found.'
        )

try:
    from uniseg.graphemecluster import grapheme_clusters
except ImportError:
    logging.warning(
        'Module `uniseg` not found. Grapheme clusters may not render correctly.'
    )
    def grapheme_clusters(text):
        """Use NFC as poor-man's grapheme cluster. This works... sometimes."""
        for c in normalize('NFC', text):
            yield c

from .binary import ceildiv
from .labels import Char, Codepoint
from .raster import Raster
from .properties import Props
from .glyph import Glyph
from .glyphmap import GlyphMap


DIRECTIONS = {
    'n': 'normal',
    'l': 'left-to-right',
    'r': 'right-to-left',
    't': 'top-to-bottom',
    'b': 'bottom-to-top'
}

ALIGNMENTS = {
    'l': 'left',
    'r': 'right',
    't': 'top',
    'b': 'bottom'
}



###############################################################################
# text rendering

def render(
        font, text, *, margin=None, adjust_bearings=0,
        direction='', align='',
        missing='default', transformations=(),
    ):
    """Render text string to bitmap."""
    direction, line_direction, base_direction, align = _get_direction(
        font, text, direction, align
    )
    # get glyph rows for rendering (tuple of tuples)
    glyphs = _get_text_glyphs(
        font, text, direction, line_direction, base_direction, missing
    )
    # subset font to glyphs needed only
    if transformations:
        # apply transformations to subsetted font
        # note we keep the original font as implied line metrics can differ
        rfont = font.modify(_g for _row in glyphs for _g in _row)
        for func, args, kwargs in transformations:
            rfont = func(rfont, *args, **kwargs)
        # get glyph rows again, from transformed font
        glyphs = _get_text_glyphs(
            rfont, text, direction, line_direction, base_direction, missing
        )
    # reduce all glyphs to avoid creating overwide margins
    glyphs = tuple(
        tuple(_g.reduce(create_vertical_metrics=True) for _g in _row)
        for _row in glyphs
    )
    if direction in ('top-to-bottom', 'bottom-to-top'):
        _render = _render_vertical
        min_margin = 0, _adjust_margins_vertical(glyphs)
    else:
        _render = _render_horizontal
        min_margin = _adjust_margins_horizontal(glyphs), 0
    margin_x, margin_y = margin or min_margin
    glyph_map = _render(
        font, glyphs, margin_x, margin_y, align, adjust_bearings
    )
    return glyph_map

def _adjust_margins_horizontal(glyphs):
    """Ensure margins are wide enough for any negative bearings."""
    glyphs = tuple(_row for _row in glyphs if _row)
    if not glyphs:
        return 0
    min_left = min(_row[0].left_bearing for _row in glyphs)
    min_right = min(_row[-1].right_bearing for _row in glyphs)
    return -min(0, min_left, min_right)

def _adjust_margins_vertical(glyphs):
    """Ensure margins are wide enough for any negative bearings."""
    glyphs = tuple(_row for _row in glyphs if _row)
    if not glyphs:
        return 0
    min_top = min(_row[0].top_bearing for _row in glyphs)
    min_bottom = min(_row[-1].bottom_bearing for _row in glyphs)
    return -min(0, min_top, min_bottom)


def _render_horizontal(
        font, glyphs, margin_x, margin_y, align, adjust_bearings
    ):
    """Render text horizontally."""
    # descent-line of the bottom-most row is at bottom margin
    # if a glyph extends below the descent line or left of the origin,
    # it may draw into the margin
    baseline = -margin_y - font.ascent
    glyph_map = GlyphMap()
    # append empty glyph at start and end for margins
    glyph_map.append_glyph(Glyph(), 0, 0, sheet=0)
    for glyph_row in glyphs:
        # x, y are relative to the left margin & baseline
        x = 0
        grid_x, grid_y = [], []
        for count, glyph in enumerate(glyph_row):
            # adjust origin for kerning
            if count:
                x += adjust_bearings
                x += round(prev.right_kerning.get_for_glyph(glyph))
                x += round(glyph.left_kerning.get_for_glyph(prev))
            prev = glyph
            # offset + (x, y) is the coordinate of glyph matrix origin
            grid_x.append(glyph.left_bearing + x)
            grid_y.append(glyph.shift_up + baseline)
            # advance origin to next glyph
            x += glyph.advance_width
        if align == 'right':
            start = -margin_x - x
        else:
            start = margin_x
        # append empty glyph at start and end for margins
        glyph_map.append_glyph(
            Glyph(), start+x+margin_x, baseline-font.descent-margin_y, sheet=0,
        )
        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            glyph_map.append_glyph(glyph, start+x, y, sheet=0)
        # move to next line
        baseline -= font.line_height
    return glyph_map


def _render_vertical(
        font, glyphs, margin_x, margin_y, align, adjust_bearings
    ):
    """Render text vertically."""
    # central axis (with leftward bias)
    baseline = font.line_width // 2
    # default is ttb right-to-left
    glyph_map = GlyphMap()
    glyph_map.append_glyph(Glyph(), 0, 0, sheet=0)
    for glyph_row in glyphs:
        y = 0
        grid_x, grid_y = [], []
        for count, glyph in enumerate(glyph_row):
            # advance origin to next glyph
            if count:
                y -= adjust_bearings
            y -= glyph.advance_height
            grid_y.append(y + glyph.bottom_bearing)
            grid_x.append(baseline - (glyph.width//2) - glyph.shift_left)
        if align == 'bottom':
            start = margin_y - y
        else:
            start = -margin_y
        # append empty glyph at start and end for margins
        glyph_map.append_glyph(
            Glyph(),
            x=baseline + (font.line_width+1)//2 + margin_x*2,
            y=start+y-margin_y,
            sheet=0,
        )
        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            glyph_map.append_glyph(glyph, margin_x+x, start+y, sheet=0)
        # move to next line
        baseline += font.line_width
    return glyph_map


def _get_direction(font, text, direction, align):
    """Get direction and alignment."""
    isstr = isinstance(text, str)
    if not direction:
        if isstr:
            direction = 'n'
        else:
            direction = font.direction or 'l'
    direction = direction.lower()
    force = direction.split(' ')[-1].startswith('f')
    if force:
        direction, _, _ = direction.rpartition(' ')
    # get line advance direction if given
    direction, _, line_direction = direction.partition(' ')
    try:
        direction = DIRECTIONS[direction[0]]
    except KeyError:
        raise ValueError(
            'Writing direction must be one of '
            + ', '.join(
                f'`{_k}`==`{_v}`'
                for _k, _v in DIRECTIONS.items()
            )
            + f'; not `{direction}`.'
        )
    if not line_direction or line_direction.startswith('n'):
        if direction == 'top-to-bottom':
            line_direction = 'r'
        else:
            line_direction = 't'
    try:
        line_direction = DIRECTIONS[line_direction[0]]
    except KeyError:
        raise ValueError(
            'Line direction must be one of '
            + ', '.join(
                f'`{_k}`==`{_v}`'
                for _k, _v in DIRECTIONS.items()
            )
            + f'; not `{direction}`.'
        )
    # determine base drection
    if isstr and not force:
        if direction in ('left-to-right', 'right-to-left'):
            # for Unicode text with horizontal directions, always use bidi algo
            # direction parameter is taken as *base direction* only
            base_direction = direction
            direction = 'normal'
        else:
            # use the class of the first directional character encountered
            base_level = get_base_level(text)
            base_direction = ('left-to-right', 'right-to-left')[base_level]
    else:
        if direction == 'normal':
            if not isstr:
                raise ValueError(
                    f'Writing direction `{direction}` only supported for Unicode text.'
                )
            else:
                raise ValueError(
                    f'Writing direction `{direction}` not supported with `force`.'
                )
        base_direction = direction
    # determine alignment
    if align:
        align = ALIGNMENTS[align[0].lower()]
    if not align:
        if direction == 'left-to-right':
            align = 'left'
        elif direction == 'right-to-left':
            align = 'right'
        elif direction == 'normal':
            if base_direction == 'left-to-right':
                align = 'left'
            else:
                align = 'right'
        elif direction == 'bottom-to-top':
            align = 'bottom'
        else:
            align = 'top'
    return direction, line_direction, base_direction, align


def _get_text_glyphs(
        font, text,
        direction, line_direction, base_direction,
        missing='raise'
    ):
    """
    Get tuple of tuples of glyphs (by line) from str or bytes/codepoints input.
    Glyphs are reordered so that they can be rendered ltr ttb or ttb ltr
    """
    if isinstance(text, str) and direction not in ('top-to-bottom', 'bottom-to-top'):
        # reshape Arabic glyphs to contextual forms
        try:
            text = reshape(text)
        except ImportError as e:
            # check common Arabic range - is there anything to reshape?
            if any(ord(_c) in range(0x600, 0x700) for _c in text):
                logging.warning(e)
        # put characters in visual order instead of logical
        if direction == 'normal':
            # decide direction based on bidi algorithm
            base_dir = {
                'left-to-right': 'L',
                'right-to-left': 'R'
            }[base_direction]
            text = get_display(text, base_dir=base_dir)
    lines = text.splitlines()
    if direction in ('right-to-left', 'bottom-to-top'):
        # reverse glyph order for rendering
        lines = tuple(_row[::-1] for _row in lines)
    if line_direction in ('right-to-left', 'bottom-to-top'):
        # reverse line order for rendering
        lines = lines[::-1]
    return tuple(
        tuple(_iter_labels(font, _line, missing))
        for _line in lines
    )

def _iter_labels(font, text, missing='raise'):
    """Iterate over labels in text, yielding glyphs. text may be str or bytes."""
    if isinstance(text, str):
        font = font.label()
        # split text into standard grapheme clusters
        text = tuple(grapheme_clusters(text))
        # find the longest *number of standard grapheme clusters* per label
        # this will often be 1, except when the font has defined e.g. Zł or Ft
        # as a char label for a single glyph
        labelset = font.get_chars()
        max_length = max((len(tuple(grapheme_clusters(_c))) for _c in labelset), default=0)
        # we need to combine multiple elements back into str to match a glyph
        def labeltype(seq):
            return Char(''.join(seq))
    else:
        font = font.label(codepoint_from=font.encoding)
        labelset = font.get_codepoints()
        labeltype = Codepoint
        max_length = max((len(_c) for _c in labelset), default=0)
    remaining = text
    while remaining:
        # try multibyte/multi-grapheme cluster clusters first
        for try_len in range(max_length, 1, -1):
            label = labeltype(remaining[:try_len])
            # what about combining chars?
            # - For str text, we iterate over grapheme clusters already,
            #   so we really only want multi-grapheme cluster clusters
            #   if they're actually defined in the font. Note that grapheme clusters
            #   may well be realised through combining glyphs.
            # - For bytes, we'll do the same. So there is no auto-combining glyphs
            #   in bytes-based fonts, they have to be provided as MBCS in the font.
            if try_len > 1 and label not in labelset:
                continue
            try:
                # convert to explicit label type,
                # avoids matching tags as well as chars
                yield font.get_glyph(label, missing='raise')
            except KeyError:
                pass
            else:
                remaining = remaining[try_len:]
                break
        else:
            yield font.get_glyph(labeltype(remaining[:1]), missing=missing)
            remaining = remaining[1:]
