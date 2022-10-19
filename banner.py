#!/usr/bin/env python3
"""
Print a banner using a bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""


import sys
import argparse
import logging
from codecs import escape_decode

import monobit
from monobit.scripting import pair, main
from monobit import render_text


def unescape(text):
    """Interpolate escape sequences."""
    # escape_decode is undocumented/unsupported and will leave \u escapes untouched
    # simpler variant - using documented/supported codecs
    #   raw-unicode-escape encodes to latin-1, leaves existing backslashes untouched but escapes non-latin-1
    #   (while unicode-escape would escape backslashes and all non-ascii)
    #   unicode-escape decodes from latin-1 and unescapes standard c escapes, \x.. and \u.. \U..
    return text.encode('raw-unicode-escape').decode('unicode_escape')


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument(
    'text', nargs='*', type=str,
    help='text to be printed. multiple text arguments represent consecutive lines. if not given, read from standard input'
)
parser.add_argument(
    '--font', '-f', type=str, default='',
    help='font file to use when printng text'
)
parser.add_argument(
    '--format', type=str, default='',
    help='format of file used in --font'
)
parser.add_argument(
    '--ink', '--foreground', '-fg', type=str, default='@',
    help='character to use for ink/foreground (default: @)'
)
parser.add_argument(
    '--paper', '--background', '-bg', type=str, default='.',
    help='character to use for paper/background (default: .)'
)
parser.add_argument(
    '--margin', '-m', type=pair, default=(0, 0),
    help='number of background characters to use as a margin in x and y direction (default: 0,0)'
)
parser.add_argument(
    '--scale', '-s', type=pair, default=(1, 1),
    help='number of characters to use per pixel in x and y direction (default: 1,1)'
)
parser.add_argument(
    '--rotate', '-r', type=int, default=0,
    help='number of quarter turns to rotate (default: 0)'
)
parser.add_argument(
    '--direction', type=str, default='',
    help=(
        "writing direction (default: use bidirectional algorithm;"
        " other options: `left-to-right`, `right-to-left`, `reverse`)"
    )
)
parser.add_argument(
    '--encoding', default='', type=str,
    help='override encoding/codepage (default: infer from metadata in file)'
)
parser.add_argument(
    '--chart', action='store_true',
    help="output codepage chart for lowest 256 codepoints. Can't be used with text or --encoding"
)
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)

args = parser.parse_args()


with main(args.debug):
    # codepage chart
    if args.chart:
        if args.text or args.encoding:
            raise ValueError("Can't supply text or `--encoding` with `--chart`.")
        args.text = b'\n'.join(bytes(range(_row, _row+16)) for _row in range(0, 256, 16))
        args.encoding = '_'
    # read text from stdin if not supplied
    elif not args.text:
        args.text = sys.stdin.read()
    else:
        # multiple options or \n give line breaks
        args.text = '\n'.join(args.text)
    # foreground and backgound characters
    args.ink = unescape(args.ink)
    args.paper = unescape(args.paper)
    args.text = unescape(args.text)
    # take first font from pack
    font, *_ = monobit.load(args.font, format=args.format)
    # check if any characters are defined
    # override encoding if requested
    if not font.get_chars() and not args.encoding and not isinstance(args.text, bytes):
        logging.info(
            'No character mapping defined in font. Using `--encoding=raw` as fallback.'
        )
        args.encoding = 'raw'
    if args.encoding == 'raw':
        # use string as a representation of bytes, replace anything with more than 8-bit codepoints
        args.text = args.text.encode('latin-1', errors='replace')
    elif args.encoding:
        font = font.modify(encoding=args.encoding).label()
    sys.stdout.write(render_text(
        font, args.text, args.ink, args.paper,
        margin=args.margin, scale=args.scale, rotate=args.rotate, direction=args.direction,
        missing='default'
    ) + '\n')
