"""
monobit.operations - manipulate glyphs

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def mirror(glyphs):
    """Reverse pixels horizontally."""
    return {
        _key: [_row[::-1] for _row in _char]
        for _key, _char in glyhps.items()
    }

def flip(glyphs):
    """Reverse pixels vertically."""
    return {
        _key: _char[::-1]
        for _key, _char in glyhps.items()
    }

def transpose(glyphs):
    """Transpose glyphs."""
    return {
        _key: [list(_x) for _x in zip(*a)]
        for _key, _char in glyhps.items()
    }

def rotate(glyphs, turns):
    """Rotate by 90-degree turns; positive is counterclockwise."""
    turns %= 4
    if turns == 3:
        return flip(transpose(glyphs))
    elif turns == 2:
        return flip(mirror(glyphs))
    elif turns == 1:
        return mirror(transpose(glyphs))
    return glyphs

def invert(glyphs):
    """Reverse video."""
    return {
        _key: [[(not _col) for _col in _row] for _row in _char]
        for _key, _char in glyhps.items()
    }

def crop(glyphs, left=0, top=0, right=None, bottom=None):
    """Crop glyphs, inclusive bounds."""
    return {
        _key: [_row[left: right] for _row in _char[top:bottom]]
        for _key, _char in glyhps.items()
    }

def stretch(glyphs, factor_x=1, factor_y=1):
    """Repeat rows and/or columns."""
    # vertical stretch
    glyphs = {
        _key: [_row for _row in _char for _ in range(factor_y)]
        for _key, _char in glyhps.items()
    }
    # horizontal stretch
    glyphs = {
        _key: [
            [_col for _col in _row for _ in range(factor_x)]
            for _row in _char
        ]
        for _key, _char in glyhps.items()
    }
    return glyphs

def shrink(glyphs, factor_x=1, factor_y=1):
    """Remove rows and/or columns."""
    # vertical shrink
    glyphs = {
        _key: _char[::factor_y]
        for _key, _char in glyphs.items()
    }
    # horizontal stretch
    glyphs = {
        _key: [_row[::factor_x] for _row in _char]
        for _key, _char in glyphs.items()
    }
    return glyphs
