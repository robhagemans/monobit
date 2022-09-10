#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args


###################################################################################################
# argument parsing

# parse command line
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('infile', nargs='?', type=str, default='')
parser.add_argument('outfile', nargs='?', type=str, default='')
parser.add_argument(
    '--from', dest='from_', default='', type=str,
    help='input format (default: infer from magic number or filename)'
)
parser.add_argument(
    '--to', dest='to_', default='', type=str,
    help='output format (default: infer from filename)'
)
parser.add_argument(
    '--encoding', default='', type=str,
    help='override encoding/codepage (default: infer from metadata in file)'
)
parser.add_argument(
    '--comments', default='', type=str,
    help='add global comments from text file'
)
parser.add_argument(
    '--overwrite', action='store_true',
    help='overwrite existing output file'
)
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)

args, _ = parser.parse_known_args()


loader_args = monobit.loaders.get_args(format=args.from_)
saver_args = monobit.savers.get_args(format=args.to_)
add_script_args(parser, loader_args, args.from_, 'load')
add_script_args(parser, saver_args, args.to_, 'save')

# to ensure loader / saver arguments are included in help
# we should only parse it after adding those
parser.add_argument(
    '-h', '--help', action='store_true',
    help='show this help message and exit'
)

args = parser.parse_args()

if args.help:
    parser.print_help()
    sys.exit(0)


###################################################################################################
# main operation

with main(args, logging.INFO):

    # if no infile or outfile provided, use stdio
    infile = args.infile or sys.stdin
    outfile = args.outfile or sys.stdout

    pack = monobit.load(infile, format=args.from_, **loader_args.pick(args))

    # set encoding
    if args.encoding:
        pack = tuple(_font.set(encoding=args.encoding) for _font in pack)
    # add comments
    if args.comments:
        with open(args.comments) as f:
            pack = tuple(_font.add(comments=f.read()) for _font in pack)

    monobit.save(pack, outfile, overwrite=args.overwrite, format=args.to_, **saver_args.pick(args))
