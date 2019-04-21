#!/usr/bin/env python3
"""
Invert font in a hexdraw text file
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
args = parser.parse_args()

font = monobit.hexdraw.load(args.infile)
font = monobit.invert(font)
monobit.hexdraw.save(font, args.outfile)
