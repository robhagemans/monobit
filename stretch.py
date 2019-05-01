#!/usr/bin/env python3
"""
Stretch font
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
    help='horizontal stretch factor, must be integer >= 1'
)
parser.add_argument(
    '-y', '--factor-y', default=1, type=int,
    help='vertical stretch factor, must be integer >= 1'
)
args = parser.parse_args()

font = monobit.load(args.infile)
font = monobit.stretch(font, factor_x=args.factor_x, factor_y=args.factor_y)
font.save(args.outfile)
