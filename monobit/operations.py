"""
monobit.operations - manipulate glyphs

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def mirror(glyph):
    """Reverse pixels horizontally."""
    return [_row[::-1] for _row in glyph]

def flip(glyph):
    """Reverse pixels vertically."""
    return glyph[::-1]

def transpose(glyph):
    """Transpose glyph."""
    return [list(_x) for _x in zip(*glyph)]

def rotate(glyph, turns):
    """Rotate by 90-degree turns; positive is clockwise."""
    turns %= 4
    if turns == 3:
        return flip(transpose(glyph))
    elif turns == 2:
        return flip(mirror(glyph))
    elif turns == 1:
        return mirror(transpose(glyph))
    return glyph

def invert(glyph):
    """Reverse video."""
    return [[(not _col) for _col in _row] for _row in glyph]

def crop(glyph, left=0, top=0, right=0, bottom=0):
    """Crop glyph, inclusive bounds."""
    return [
        _row[left : (-right if right else None)]
        for _row in glyph[top : (-bottom if bottom else None)]
    ]

def expand(glyph, left=0, top=0, right=0, bottom=0):
    """Add empty space."""
    if glyph:
        old_width = len(glyph[0])
    else:
        old_width = 0
    new_width = left + old_width + right
    return (
        [[False] * new_width for _ in range(top)]
        + [[False] * left + _row + [False] * right for _row in glyph]
        + [[False] * new_width for _ in range(bottom)]
    )

def stretch(glyph, factor_x=1, factor_y=1):
    """Repeat rows and/or columns."""
    # vertical stretch
    glyph = [_row for _row in glyph for _ in range(factor_y)]
    # horizontal stretch
    glyph = [
        [_col for _col in _row for _ in range(factor_x)]
        for _row in glyph
    ]
    return glyph

def shrink(glyph, factor_x=1, factor_y=1, force=False):
    """Remove rows and/or columns."""
    # vertical shrink
    shrunk_glyph = glyph[::factor_y]
    if not force:
        # check we're not throwing away stuff
        for offs in range(1, factor_y):
            alt = glyph[offs::factor_y]
            if shrunk_glyph != alt:
                raise ValueError("can't shrink glyph without loss")
    # horizontal stretch
    glyph = [_row[::factor_x] for _row in glyph]
    return glyph
