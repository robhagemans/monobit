#!/usr/bin/env python3
"""
Draw monospace bitmap font to image
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging
import string
from PIL import Image

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# background and foreground symbols in .draw file
BGCHAR = u'-'
FGCHAR = u'#'

BG = (0, 0, 0)
FG = (255, 255, 255)


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

# drop all comments
codelines = [
    _line
    for _line in args.infile.readlines()
    if _line and _line[0] in ' \t' + string.hexdigits
]

# cluster by character
# assuming only one code point per glyph, for now
clusters = []
for line in codelines:
    if line[0] in string.hexdigits:
        cp, rest = line.strip().split(':')
        if rest:
            clusters.append((cp, [rest.strip()]))
        else:
            clusters.append((cp, []))
    else:
        clusters[-1][1].append(line.strip())

glyphs = {int(_cluster[0], 16): _cluster[1] for _cluster in clusters}


# work out image geometry
# assume all glyphs have the same size, for now.
step_x = len(clusters[0][1][0])*args.scale_x + args.padding_x
step_y = len(clusters[0][1])*args.scale_y + args.padding_y

# ceildiv
rows = -(-(max(glyphs.keys())+1) // args.columns)

width = args.columns * step_x + 2 * args.margin_x - args.padding_x
height = rows * step_y + 2* args.margin_y - args.padding_y

img = Image.new('RGB', (width, height), (32, 32, 32))

for row in range(rows):
    for col in range(args.columns):
        ordinal = row * args.columns + col
        try:
            glyph = glyphs[ordinal]
        except KeyError:
            continue
        charimg = Image.new('RGB', (len(glyph[0]), len(glyph)))
        data = [
            BG if _c == BGCHAR else FG
            for _row in glyph
            for _c in _row
        ]
        charimg.putdata(data)
        charimg = charimg.resize((charimg.width * args.scale_x, charimg.height * args.scale_y))
        lefttop = (args.margin_x+col*step_x, args.margin_y + row*step_y)
        img.paste(charimg, lefttop)

if not args.outfile:
    img.show()
else:
    img.save(args.outfile)
