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
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('infile', nargs='?', type=str, default='')
parser.add_argument('outfile', nargs='?', type=str, default='')
parser.add_argument(
    '--from', dest='from_', default='', type=str,
    help='input format (default: infer from filename)'
)
parser.add_argument(
    '--to', dest='to_', default='', type=str,
    help='output format (default: infer from filename)'
)
parser.add_argument(
    '--codepage', default='', type=str,
    help='override codepage (default: infer from metadata in file)'
)
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)
parser.add_argument(
    '-h', '--help', action='store_true',
    help='show this help message and exit'
)
# find out which operation we're asked to perform
args, unknown = parser.parse_known_args()

# get loader arguments
loader = monobit.Typeface.get_loader(args.infile, format=args.from_)
for arg, _type in loader.script_args.items():
    parser.add_argument('--' + arg.replace('_', '-'), dest=arg, type=_type)

# get saver arguments
saver = monobit.Typeface.get_saver(args.outfile, format=args.to_)
for arg, _type in saver.script_args.items():
    parser.add_argument('--' + arg.replace('_', '-'), dest=arg, type=_type)

args = parser.parse_args()

if args.help:
    parser.print_help()
    sys.exit(0)

# convert arguments to type accepted by operation
load_args = {
    _name: _arg
    for _name, _arg in vars(args).items()
    if _arg is not None and _name in loader.script_args
}
save_args = {
    _name: _arg
    for _name, _arg in vars(args).items()
    if _arg is not None and _name in saver.script_args
}


if args.debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')

try:
    font = monobit.load(args.infile, format=args.from_, **load_args)
    if args.codepage:
        font = font.set_encoding(args.codepage)
    font.save(args.outfile, format=args.to_, **save_args)
except Exception as exc:
    logging.error(exc)
    if args.debug:
        raise
