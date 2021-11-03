#!/usr/bin/env python3
"""
Print a banner using a bitmap font
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
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
    # escape_decode is unofficial/unsupported
    # https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python
    return escape_decode(text.encode('utf-8'))[0].decode('utf-8')

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument(
    'text', nargs='?', type=str,
    help='text to be printed. if not given, read from standard input'
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
    '--paper', '--background', '-bg', type=str, default='-',
    help='character to use for paper/background (default: -)'
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


with main(args, logging.WARNING):
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
        args.text = unescape(args.text)
    # foreground and backgound characters
    args.ink = unescape(args.ink)
    args.paper = unescape(args.paper)
    # take first font from pack
    font, *_ = monobit.load(args.font, format=args.format)
    # check if any characters are defined
    # override encoding if requested
    if not font.get_chars() and not args.encoding and not isinstance(args.text, bytes):
        logging.info(
            'No character mappeing defined in font. Using `--encoding=raw` as fallback.'
        )
        args.encoding = 'raw'
    if args.encoding == 'raw':
        # use string as a representation of bytes
        args.text = args.text.encode('latin-1', errors='ignore')
    elif args.encoding:
        font = font.modify(encoding=args.encoding)
    sys.stdout.write(render_text(
        font, args.text, args.ink, args.paper,
        margin=args.margin, scale=args.scale, rotate=args.rotate, missing='default'
    ) + '\n')
