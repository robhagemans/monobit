#!/usr/bin/env python3
"""
Crop font
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=str, default='')
parser.add_argument('outfile', nargs='?', type=str, default='')
parser.add_argument(
    '--left', default=0, type=int,
    help='first pixel on left'
)
parser.add_argument(
    '--top', default=0, type=int,
    help='first pixel from top'
)
parser.add_argument(
    '--right', default=None, type=int,
    help='last pixel on right'
)
parser.add_argument(
    '--bottom', default=None, type=int,
    help='last pixel at bottom'
)
args = parser.parse_args()

font = monobit.load(args.infile)
font = monobit.crop(font, args.left, args.top, args.right, args.bottom)
font.save(args.outfile)
