#!/usr/bin/env python3
"""
Extract monospace bitmap font from raw binary and output as hexdraw text file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse

# background and foreground symbols in .draw file
BGCHAR = u'-'
FGCHAR = u'#'


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin.buffer)
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
    '-n', '--number', nargs=1, default=None, type=lambda _s: int(_s, 0),
    help='number of characters to extract'
)
parser.add_argument(
    '--offset', default=0, type=lambda _s: int(_s, 0),
    help='bytes offset into binary'
)
parser.add_argument(
    '--padding', default=0, type=int,
    help='number of scanlines between characters to discard'
)
parser.add_argument(
    '--clip-x', default=0, type=int,
    help='number of pixels on the left of character to discard'
)
parser.add_argument(
    '--mirror', action='store_true', default=False,
    help='reverse bits horizontally'
)
parser.add_argument(
    '--invert', action='store_true', default=False,
    help='invert foreground and background'
)
args = parser.parse_args()

if args.invert:
    FGCHAR, BGCHAR = BGCHAR, FGCHAR

rombytes = args.infile.read()
rombytes = rombytes[args.offset:]
rows = [u'{:08b}'.format(_c) for _c in bytearray(rombytes)]
drawn = [_row.replace(u'0', BGCHAR).replace(u'1', FGCHAR) for _row in rows]

full_height = args.height + args.padding
if args.number:
    n_chars = args.number[0]
else:
    n_chars = (len(rows) + args.padding) // full_height
width_bytes = (args.width+7) // 8


for ordinal in range(n_chars):
    char = drawn[ordinal*width_bytes*full_height : (ordinal+1)*width_bytes*full_height]
    # remove vertical padding
    char = char[:args.height*width_bytes]
    char = [
        u''.join(char[_offset:_offset+width_bytes])
        for _offset in range(0, len(char), width_bytes)
    ]
    # mirror if necessary
    if args.mirror:
        char = [_row[::-1] for _row in char]
    # remove horizontal padding
    char = [_row[args.clip_x:args.clip_x+args.width] for _row in char]
    # output
    args.outfile.write(u'{:02x}:\n\t'.format(ordinal))
    args.outfile.write(u'\n\t'.join(char))
    args.outfile.write(u'\n\n')
