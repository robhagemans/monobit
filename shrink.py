#!/usr/bin/env python3
"""
Shrink font
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '-x', '--factor-x', default=1, type=int,
    help='horizontal shrink factor, must be integer >= 1'
)
parser.add_argument(
    '-y', '--factor-y', default=1, type=int,
    help='vertical shrink factor, must be integer >= 1'
)
parser.add_argument(
    '-f', '--force', action='store_true',
    help='shrink even if this causes loss of information'
)
args = parser.parse_args()

font = monobit.load(args.infile)
font = monobit.shrink(font, factor_x=args.factor_x, factor_y=args.factor_y, force=args.force)
font.save(args.outfile)
