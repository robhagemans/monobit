#!/usr/bin/env python3
"""
Draw monospace bitmap font to image
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
parser.add_argument('outfile', nargs='?', default=None)
parser.add_argument(
    '--padding-x', default=0, type=int,
    help='number of horizontal pixels between character cells'
)
parser.add_argument(
    '--padding-y', default=0, type=int,
    help='number of vertical pixels between character cells'
)
parser.add_argument(
    '--margin-x', default=0, type=int,
    help='number of horizontal pixels left of first character cell'
)
parser.add_argument(
    '--margin-y', default=0, type=int,
    help='number of vertical pixels above first character cell'
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
    '--columns', default=32, type=int,
    help='number of columns in output'
)
args = parser.parse_args()
kwargs = dict(
    columns=args.columns, margin=(args.margin_x, args.margin_y), padding=(args.padding_x, args.padding_y),
    scale=(args.scale_x, args.scale_y),
    border=(32, 32, 32), back=(0, 0, 0), fore=(255, 255, 255),
)


font = monobit.hexdraw.load(args.infile)

if not args.outfile:
    monobit.show(font, **kwargs)
else:
    monobit.image.save(font, args.outfile, **kwargs)
