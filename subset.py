#!/usr/bin/env python3
"""
Expand font in a hexdraw text file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


# parse command line
anyint = lambda _s: int(_s, 0)
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '--from', default=0, dest='from_', type=anyint, help='first character to take'
)
parser.add_argument(
    '--to', default=-1, dest='to_', type=anyint, help='last character to take (inclusive)'
)
args = parser.parse_args()

font = monobit.hexdraw.load(args.infile)
font = {
    _k: _v
    for _k, _v in font.items()
    if _k >= args.from_ and args.to_ < 0 or _k <= args.to_
}
monobit.hexdraw.save(font, args.outfile)
