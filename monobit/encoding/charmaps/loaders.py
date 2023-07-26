"""
monobit.encoding.charmaps.loaders - character map loaders

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from html.parser import HTMLParser

from ...binary import int_to_bytes
from .charmapclass import register_reader


@register_reader('txt')
@register_reader('enc')
@register_reader('map')
@register_reader('ucp', separator=':', joiner=',')
@register_reader('adobe', separator='\t', joiner=None, codepoint_column=1, unicode_column=0)
def _from_text_columns(
        data, *, comment='#', separator=None, joiner='+', codepoint_column=0, unicode_column=1,
        codepoint_base=16, unicode_base=16, inline_comments=True, ignore_errors=False,
    ):
    """Extract character mapping from text columns in file data (as bytes)."""
    mapping = {}
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('START') or line.startswith('END'):
            # xfonts .enc files - STARTENCODING, STARTMAPPING etc.
            continue
        # strip off comments
        if inline_comments:
            line = line.split(comment)[0]
        # split unicodepoint and hex string
        splitline = line.split(separator)
        if len(splitline) > max(codepoint_column, unicode_column):
            cp_str, uni_str = splitline[codepoint_column], splitline[unicode_column]
            cp_str = cp_str.strip()
            uni_str = uni_str.strip()
            # right-to-left marker in mac codepages
            uni_str = uni_str.replace('<RL>+', '').replace('<LR>+', '')
            # reverse-video marker in kreativekorp codepages
            uni_str = uni_str.replace('<RV>+', '')
            # czyborra's codepages have U+ in front
            if uni_str.upper().startswith('U+'):
                uni_str = uni_str[2:]
            # ibm-ugl codepage has U in front
            if uni_str.upper().startswith('U'):
                uni_str = uni_str[1:]
            # czyborra's codepages have = in front
            if cp_str.upper().startswith('='):
                cp_str = cp_str[1:]
            try:
                # allow sequence of codepoints
                # multibyte code points can also be given as single large number
                # note that the page bytewidth of the codepoints is assumed to be 1
                cp_point = b''.join(
                    int_to_bytes(int(_substr, codepoint_base))
                    for _substr in cp_str.split(joiner)
                )
                if unicode_base == 'char':
                    # the character itself is in the column, utf-8 encoded
                    char = uni_str
                else:
                    # allow sequence of unicode code points separated by 'joiner'
                    char = ''.join(
                        chr(int(_substr, unicode_base))
                        for _substr in uni_str.split(joiner)
                    )
                if char != '\uFFFD':
                    # u+FFFD replacement character is used to mark undefined code points
                    mapping[cp_point] = char
            except (ValueError, TypeError) as e:
                # ignore malformed lines
                if not ignore_errors:
                    logging.warning('Could not parse line in text charmap file: %s [%s]', e, repr(line))
    return mapping


@register_reader('ucm')
def _from_ucm_charmap(data):
    """Extract character mapping from icu ucm / linux charmap file data (as bytes)."""
    # only deals with sbcs
    comment = '#'
    escape = '\\'
    # precision indicator
    precision = '|'
    mapping = {}
    parse = False
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('<comment_char>'):
            comment = line.split()[-1].strip()
        elif line.startswith('<escape_char>'):
            escape = line.split()[-1].strip()
        elif line.startswith('CHARMAP'):
            parse = True
            continue
        elif line.startswith('END CHARMAP'):
            parse = False
        if not parse:
            continue
        # split columns
        splitline = line.split()
        # ignore malformed lines
        exc = ''
        cp_bytes, uni_str = '', ''
        for item in splitline:
            if item.startswith('<U'):
                # e.g. <U0000> or <U2913C>
                uni_str = item[2:-1]
            elif item.startswith(escape + 'x'):
                cp_str = item.replace(escape + 'x', '')
                cp_bytes = bytes.fromhex(cp_str)
            elif item.startswith(precision):
                # precision indicator
                # |0 - A “normal”, roundtrip mapping from a Unicode code point and back.
                # |1 - A “fallback” mapping only from Unicode to the codepage, but not back.
                # |2 - A subchar1 mapping. The code point is unmappable, and if a substitution is
                #      performed, then the subchar1 should be used rather than the subchar.
                #      Otherwise, such mappings are ignored.
                # |3 - A “reverse fallback” mapping only from the codepage to Unicode, but not back
                #      to the codepage.
                # |4 - A “good one-way” mapping only from Unicode to the codepage, but not back.
                if item[1:].strip() != '0':
                    # only accept 'normal' mappings
                    # should we also allow "reverse fallback" ?
                    break
        else:
            if not uni_str or not cp_str:
                logging.warning('Could not parse line in ucm charmap file: %s.', repr(line))
                continue
            if cp_bytes in mapping:
                logging.debug('Ignoring redefinition of code point %s', cp_bytes)
            else:
                mapping[cp_bytes] = chr(int(uni_str, 16))
    return mapping


@register_reader('html')
def _from_wikipedia(data, table=0, column=0, range=None):
    """
    Scrape charmap from table in Wikipedia.
    Reads matrix tables with class="chset".
    table: target table; 0 for 1st chset table, etc.
    column: target column if multiple unicode points provided per cell.
    range: range to read, read all if range is empty
    """

    class _WikiParser(HTMLParser):
        """HTMLParser object to read Wikipedia tables."""

        def __init__(self):
            """Set up Wikipedia parser."""
            super().__init__()
            # output dict
            self.mapping = {}
            # state variables
            # parsing chset table
            self.table = False
            self.count = 0
            # data element
            self.td = False
            # the unicode point is surrounded by <small> tags
            self.small = False
            # parse row header
            self.th = False
            # current codepoint
            self.current = 0

        def handle_starttag(self, tag, attrs):
            """Change state upon encountering start tag."""
            attrs = dict(attrs)
            if (
                    tag == 'table'
                    and 'class' in attrs
                    and 'chset' in attrs['class']
                ):
                if self.count == table:
                    self.table = True
                    self.th = False
                    self.td = False
                    self.small = False
                self.count += 1
            elif self.table:
                if tag == 'td':
                    self.td = True
                    self.small = False
                elif tag == 'small':
                    self.small = True
                elif tag == 'th':
                    self.th = True

        def handle_endtag(self, tag):
            """Change state upon encountering end tag."""
            if tag == 'table':
                self.table = False
                self.th = False
                self.td = False
                self.small = False
            elif tag == 'td':
                self.td = False
                self.current += 1
            elif tag == 'style':
                self.small = False
            elif tag == 'th':
                self.th = False

        def handle_data(self, data):
            """Parse cell data, depending on state."""
            # row header provides first code point of the row
            if self.th and len(data) == 2 and data[-1] == '_':
                self.current = int(data[0],16) * 16
            # unicode point in <small> tag in table cell
            if self.td and self.small:
                cols = data.split()
                if len(cols) > column:
                    data = cols[column]
                if len(data) >= 4:
                    # unicode point
                    if data.lower().startswith('u+'):
                        data = data[2:]
                    # pylint: disable=unsupported-membership-test
                    if not range or self.current in range:
                        try:
                            char = chr(int(data, 16))
                        except ValueError:
                            # not a unicode point
                            pass
                        else:
                            self.mapping[bytes((self.current,))] = char

    parser = _WikiParser()
    parser.feed(data.decode('utf-8-sig'))
    return parser.mapping
