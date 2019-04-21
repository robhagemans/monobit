#!/usr/bin/env python3
"""
Renumber glyphs in a hexdraw text file
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
parser.add_argument('--add', default=0, type=anyint, help='value to add to each ordinal')
args = parser.parse_args()

font = monobit.hexdraw.load(args.infile)
font = {
    _k+args.add: _v
    for _k, _v in font.items()
}
monobit.hexdraw.save(font, args.outfile)
