#!/usr/bin/env python3
"""
Extract monospace bitmap font from monochrome image file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', type=str, default='')
# dimensions of cell, in pixels
parser.add_argument(
    '-y', '--height', default=8, type=int,
    help='pixel height of the output character cell (after scaling)'
)
parser.add_argument(
    '-x', '--width', default=8, type=int,
    help='pixel width of the output character cell (after scaling)'
)
parser.add_argument(
    '--padding-x', default=0, type=int,
    help='number of horizontal pixels between character cells (prior to scaling)'
)
parser.add_argument(
    '--padding-y', default=0, type=int,
    help='number of vertical pixels between character cells (prior to scaling)'
)
parser.add_argument(
    '--margin-x', default=0, type=int,
    help='number of horizontal pixels left of first character cell (prior to scaling)'
)
parser.add_argument(
    '--margin-y', default=0, type=int,
    help='number of vertical pixels above first character cell (prior to scaling)'
)
parser.add_argument(
    '--scale-x', default=1, type=int,
    help='number of horizontal pixels in image that make up a pixel in the font'
)
parser.add_argument(
    '--scale-y', default=1, type=int,
    help='number of vertical pixels in image that make up a pixel in the font'
)
parser.add_argument(
    '--invert', action='store_true', default=False,
    help='invert foreground and background'
)
parser.add_argument(
    '--first', default=0, type=int,
    help='code point of first glyph in image'
)
args = parser.parse_args()

font = monobit.image.load(
    args.infile, cell=(args.width, args.height),
    margin=(args.margin_x, args.margin_y), padding=(args.padding_x, args.padding_y), scale=(args.scale_x, args.scale_y),
)
font = monobit.renumber(font, add=args.first)
if args.invert:
    font = monobit.invert(font)
font.save(args.outfile)
