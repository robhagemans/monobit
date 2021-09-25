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
args = parser.parse_args()


# load, modify, save
try:
    if not args.text:
        args.text = sys.stdin.read()
    else:
        # escape_decode is unofficial/unsupported
        # https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python
        args.text = unescape(args.text)
        args.fore = unescape(args.fore)
        args.back = unescape(args.back)
    font = monobit.load(args.font)
    # take first font from pack
    if isinstance(font, monobit.Pack):
        font, *_ = font
    sys.stdout.write(monobit.text.to_text(font.render(
        args.text, args.fore, args.back, margin=args.margin, scale=args.scale, missing='default'
    )) + '\n')
except Exception as exc:
    logging.error(exc)
