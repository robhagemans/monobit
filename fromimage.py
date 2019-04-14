#!/usr/bin/env python3
"""
Extract monospace bitmap font from monochrome image file and output as hexdraw text file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging
from PIL import Image

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# background and foreground symbols in .draw file
BGCHAR = u'-'
FGCHAR = u'#'


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
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


img = Image.open(args.infile)

# work out image geometry
step_x = args.width*args.scale_x + args.padding_x
step_y = args.height*args.scale_y + args.padding_y
# maximum number of cells that fits
ncells_x = (img.width - args.margin_x) // step_x
ncells_y = (img.height - args.margin_y) // step_y

# extract sub-images
# assume row-major left-to-right top-to-bottom
crops = [
    img.crop((
        args.margin_x + _col*step_x,
        args.margin_y + _row*step_y,
        args.margin_x + _col*step_x + args.width*args.scale_x,
        args.margin_y + _row*step_y + args.height*args.scale_y,
    ))
    for _row in range(ncells_y)
    for _col in range(ncells_x)
]

# scale
crops = [_crop.resize((args.width, args.height)) for _crop in crops]

# get pixels
crops = [list(_crop.getdata()) for _crop in crops]

# check that cells are monochrome
colourset = set.union(*(set(_data) for _data in crops))
if len(colourset) > 2:
    logging.warning('image payload is not monochrome, results will be bad')

# replace colours with characters
# top-left pixel of first char assumed to be background colour
bg = crops[0][0]
if args.invert:
    BGCHAR, FGCHAR = FGCHAR, BGCHAR
crops = [
    [BGCHAR if _c == bg else FGCHAR for _c in _cell]
    for _cell in crops
]

# reshape cells
crops = [
    [
        u''.join(_cell[_offs: _offs+args.width])
        for _offs in range(0, len(_cell), args.height)
    ]
    for _cell in crops
]
for ordinal, char in enumerate(crops):
    args.outfile.write(u'{:02x}:\n\t'.format(args.first + ordinal))
    args.outfile.write(u'\n\t'.join(char))
    args.outfile.write(u'\n\n')
