#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit

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
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)
args = parser.parse_args()

if args.debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')

try:
    font = monobit.load(args.infile, format=args.format_in)
    font.save(args.outfile, format=args.format_out)
except Exception as exc:
    logging.error(exc)
    if args.debug:
        raise
