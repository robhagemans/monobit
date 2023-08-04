"""
monobit.unicode - unicode utilities

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata


###################################################################################################
# character properties

def is_fullwidth(char):
    """Check if a character / grapheme sequence is fullwidth."""
    return any(
        unicodedata.east_asian_width(_c) in ('W', 'F')
        for _c in char
    )

def is_graphical(char):
    """Check if a char has a graphical representation."""
    return any(
        # str.isprintable includes everything but Other (C) and Separator (Z), plus SPACE
        # we keep everything but
        # Other/Control (Cc), Other/Surrogate (Cs), Separator/Line (Zl), Separator/Paragraph (Zp)
        # so we keep all spaces (Zs); PUA (Co); Other/Format (Cf) which has things like SOFT HYPHEN
        # also Not Assigned (Cn) - as unicodedata is not up to date
        # anything excluded will be dropped from our charmaps
        unicodedata.category(_c) not in ('Cc', 'Cs', 'Zl', 'Zp')
        for _c in char
    )

def is_printable(char):
    """Check if a char should be printed - nothing ambiguous or unrepresentable in there."""
    return (not char) or is_graphical(char) and all(
        # we keep everything that is_graphical except PUA, Other/Format, Not Assigned
        # anything excluded will be shown as REPLACEMENT CHARACTER
        unicodedata.category(_c) not in ('Co', 'Cf', 'Cn')
        for _c in char
    )

def is_blank(char):
    """Check if a sequence is whitespace or non-graphical."""
    if not char:
        return False
    return all(
        unicodedata.category(_c) == 'Zs' or not is_graphical(_c)
        for _c in char
    )

def is_private_use(char):
    """Check if any char is in the private use area."""
    return any(
        unicodedata.category(_c) == 'Co'
        for _c in char
    )

def unicode_name(char, no_name=''):
    """Unicode registered name."""
    names = []
    for c in char:
        try:
            names.append(unicodedata.name(c))
        except ValueError:
            names.append(no_name)
    return ', '.join(names)
