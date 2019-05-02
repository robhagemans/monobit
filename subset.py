#!/usr/bin/env python3
"""
Take glyphs from a font file
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
parser.add_argument('infile', nargs='?', type=str, default='')
parser.add_argument('outfile', nargs='?', type=str, default='')
parser.add_argument(
    '--from', default=0, dest='from_', type=anyint, help='first character to take'
)
parser.add_argument(
    '--to', default=-1, dest='to_', type=anyint, help='last character to take (inclusive)'
)
args = parser.parse_args()

font = monobit.load(args.infile)
if args.to_ < 0:
    args.to_ = font.get_max_key()
font = monobit.subset(font, range(args.from_, args._to+1))
font.save(args.outfile)
