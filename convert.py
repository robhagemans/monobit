#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
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
    '--comments', default='', type=str,
    help='add global comments from text file'
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
early_exception = None
try:
    loader = monobit.formats.Loaders.get_loader(args.infile, format=args.from_)
except Exception as exc:
    early_exception = exc
    loader = None
else:
    for arg, _type in loader.script_args.items():
        parser.add_argument('--' + arg.replace('_', '-'), dest=arg, type=_type)

# get saver arguments
try:
    saver = monobit.formats.Savers.get_saver(args.outfile, format=args.to_)
except Exception as exc:
    early_exception = exc
    saver = None
else:
    for arg, _type in saver.script_args.items():
        parser.add_argument('--' + arg.replace('_', '-'), dest=arg, type=_type)

args = parser.parse_args()

if args.help:
    parser.print_help()
    sys.exit(0)

# convert arguments to type accepted by operation
if loader:
    load_args = {
        _name: _arg
        for _name, _arg in vars(args).items()
        if _arg is not None and _name in loader.script_args
    }
else:
    load_args = {}
if saver:
    save_args = {
        _name: _arg
        for _name, _arg in vars(args).items()
        if _arg is not None and _name in saver.script_args
    }
else:
    save_args = {}


if args.debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')


try:
    if early_exception:
        raise early_exception
    if not args.infile:
        args.infile = sys.stdin.buffer
    font = monobit.load(args.infile, format=args.from_, **load_args)
    if args.codepage:
        font = font.set_encoding(args.codepage)
    if args.comments:
        with open(args.comments) as f:
            font = font.add_comments(f.read())
    if not args.outfile:
        args.outfile = sys.stdout.buffer
    monobit.save(font, args.outfile, format=args.to_, **save_args)
except BrokenPipeError:
    # happens e.g. when piping to `head`
    pass
except Exception as exc:
    logging.error(exc)
    if args.debug:
        raise
