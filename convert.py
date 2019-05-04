#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
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
    '--format-in', default='', type=str,
    help='input format (default: infer from filename)'
)
parser.add_argument(
    '--format-out', default='', type=str,
    help='output format (default: infer from filename)'
)

args = parser.parse_args()

try:
    font = monobit.load(args.infile, format=args.format_in)
    font.save(args.outfile, format=args.format_out)
except Exception as exc:
    logging.error(exc)
