#!/usr/bin/env python3
"""
Extract monospace bitmap font from raw binary
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse

import monobit

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
parser.add_argument(
    '--first', default=0, type=lambda _s: int(_s, 0),
    help='code point of first glyph in image'
)
parser.add_argument(
    '--strike', action='store_true', default=False,
    help='font is sorted in strike order (sideways). Must provide number of chars as well'
)
args = parser.parse_args()


font = monobit.raw.load(
    args.infile, cell=(args.width, args.height), n_chars=args.number[0] if args.number else None,
    offset=args.offset, strike=args.strike
)
font = monobit.renumber(font, add=args.first)
if args.invert:
    font = monobit.invert(font)
if args.mirror:
    font = monobit.mirror(font)
font = monobit.crop(font, 0, 0, args.clip_x, args.padding)
font.save(args.outfile)
