"""
monobit.text - shared utilities for text-based formats

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

def to_text(matrix, line_break='\n'):
    """Convert matrix to text."""
    return line_break.join(''.join(_row) for _row in matrix)
