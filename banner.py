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
from monobit.base import pair
from monobit.base.text import to_text


def unescape(text):
    """Interpolate escape sequences."""
    # escape_decode is unofficial/unsupported
    # https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python
    return escape_decode(text.encode('utf-8'))[0].decode('utf-8')

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('text', nargs='?', type=str)
parser.add_argument('--font', type=str, default='')
parser.add_argument('--fore', type=str, default='@')
parser.add_argument('--back', type=str, default='-')
parser.add_argument('--margin', type=pair, default=(0, 0))
parser.add_argument('--scale', type=pair, default=(1, 1))
parser.add_argument('--encoding', type=str, default='')
parser.add_argument('--chart', action='store_true')

args = parser.parse_args()

try:
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
    args.fore = unescape(args.fore)
    args.back = unescape(args.back)
    # take first font from pack
    font, *_ = monobit.load(args.font)
    # check if any characters are defined
    # override encoding if requested
    if not font.get_chars() and not args.encoding and not isinstance(args.text, bytes):
        logging.warning(
            'No character mappeing defined in font. Using `--encoding=raw` as fallback.'
        )
        args.encoding = 'raw'
    if args.encoding == 'raw':
        # use string as a representation of bytes
        args.text = args.text.encode('latin-1', errors='ignore')
    elif args.encoding:
        font = font.set_properties(encoding=args.encoding)
    sys.stdout.write(to_text(font.render(
        args.text, args.fore, args.back, margin=args.margin, scale=args.scale, missing='default'
    )) + '\n')
except Exception as exc:
    logging.error(exc)
