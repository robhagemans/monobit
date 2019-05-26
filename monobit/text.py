"""
monobit.text - shared utilities for text-based formats

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string


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
