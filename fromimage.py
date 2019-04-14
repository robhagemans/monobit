#!/usr/bin/env python3
"""
Extract monospace bitmap font from monochrome image file and output as hexdraw text file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
from PIL import Image


# background and foreground symbols in .draw file
BGCHAR = b'-'
FGCHAR = b'#'


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
# dimensions of cell, in pixels
parser.add_argument(
    '-y', '--height', default=8, type=int,
    help='pixel height of the character cell'
)
parser.add_argument(
    '-x', '--width', default=8, type=int,
    help='pixel width of the character cell'
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
args = parser.parse_args()


if args.invert:
    BGCHAR, FGCHAR = FGCHAR, BGCHAR

# read image and convert to palette bitmap
img = Image.open(args.infile).convert('P')

if args.margin_x or args.margin_y:
    # leave any margin on the right orbottom - we'll ignore it anyway
    img = img.crop((args.margin_x, args.margin_y, img.width, img.height))

# resize if needed
# FIXME: this won't work correctly with margin or padding
if args.scale_x != 1 or args.scale_y != 1:
    img = img.resize((img.width // args.scale_x, img.height // args.scale_y))

imgbytes = img.tobytes()

# assume top-left pixel of first character is background colour
bg = bytes([img.getpixel((0,0))])
# everything else is foreground
non_bg = set(imgbytes) - {bg}


# replace byte values with representations
imgbytes = imgbytes.replace(bg, BGCHAR)
for fg in non_bg:
    imgbytes = imgbytes.replace(bytes([fg]), FGCHAR)


full_width = args.width + args.padding_x
full_height = args.height + args.padding_y

rows = [
    imgbytes[_offset:_offset+img.width]
    for _offset in range(0, len(imgbytes), img.width)
]
chunkrows = [
    [
        _row[_offset : _offset+full_width]
        for _offset in range(0, len(_row), full_width)
    ]
    for _row in rows
]

n_char_cols = len(chunkrows[0])
# add one additional padding as it's only between the chars, not after
n_char_rows = (len(chunkrows) + args.padding_y) // full_height
# assume characters are arranged consecutively in rows
for crow in range(n_char_rows):
    for ccol in range(n_char_cols):
        char = [
            _chunkrow[ccol]
            for _chunkrow in chunkrows[crow*full_height : (crow+1)*full_height]
        ]
        # remove padding
        char = char[:args.height]
        char = [_row[:args.width] for _row in char]
        ordinal = crow * n_char_cols + ccol
        args.outfile.write('{:02x}:\n\t'.format(ordinal))
        args.outfile.write(b'\n\t'.join(char).decode('ascii'))
        args.outfile.write('\n\n')
