#!/usr/bin/env python3
"""
Extract monospace bitmap font from .cand output as hexdraw text file
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse

import monobit

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '--id', type=str,
    help='identifier in the c code to convert'
)
parser.add_argument(
    '-y', '--height', default=8, type=int,
    help='pixel height of the character cell'
)
parser.add_argument(
    '-x', '--width', default=8, type=int,
    help='pixel width of the character cell'
)
args = parser.parse_args()


font = monobit.c.load(args.infile, args.id, args.width, args.height)
monobit.hexdraw.save(font, args.outfile)
