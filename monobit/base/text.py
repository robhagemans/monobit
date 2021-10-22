"""
monobit.text - shared utilities for text-based formats

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

def strip_matching(from_str, char):
    """Strip a char from either side of the string if it occurs on both."""
    if not char:
        return from_str
    clen = len(char)
    if from_str.startswith(char) and from_str.endswith(char):
        return from_str[clen:-clen]
    return from_str
