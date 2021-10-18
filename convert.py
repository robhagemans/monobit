#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main

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
parser.add_argument(
    '-h', '--help', action='store_true',
    help='show this help message and exit'
)


def add_script_args(parser, loadersaver):
    """Add loader or saver arguments to argparser."""
    for arg, _type in loadersaver.script_args.items():
        parser.add_argument('--' + arg.replace('_', '-'), dest=arg, type=_type)

def convert_args(args, loadersaver):
    """Convert arguments to type accepted by operation."""
    if not loadersaver:
        return {}
    return {
        _name: _arg
        for _name, _arg in vars(args).items()
        if _arg is not None and _name in loadersaver.script_args
    }

# find out which operation we're asked to perform
args, _ = parser.parse_known_args()

# help screen should include loader/saver arguments if from/to specified
if args.help:
    if args.from_:
        loader = monobit.formats.loaders.get_loader(format=args.from_)
        add_script_args(parser, loader)
    if args.to_:
        saver = monobit.formats.savers.get_saver(format=args.to_)
        add_script_args(parser, saver)
    parser.print_help()
    sys.exit(0)


with main(args, logging.INFO):

    # if no infile or outfile provided, use stdio
    infile = args.infile or sys.stdin
    outfile = args.outfile or sys.stdout

    # open streams
    with monobit.open_location(infile, 'r') as (instream, incontainer):
        # get loader arguments
        loader = monobit.formats.loaders.get_loader(instream, format=args.from_)
        if loader:
            add_script_args(parser, loader)
            # don't raise if no loader - it may be a container we can extract
        args, _ = parser.parse_known_args()
        # convert arguments to type accepted by operation
        load_args = convert_args(args, loader)
        pack = monobit.load(instream, where=incontainer, format=args.from_, **load_args)

    # set encoding
    if args.encoding:
        pack = tuple(_font.set_encoding(args.encoding) for _font in pack)
    # add comments
    if args.comments:
        with open(args.comments) as f:
            pack = tuple(_font.add_comments(f.read()) for _font in pack)

    # record converter parameters
    pack = tuple(_font.set_properties(
        converter_parameters='convert ' + ' '.join(
            f'--{_k}={_v}'
            for _k, _v in vars(args).items()
            # exclude unset or otherwise recorded
            if _v and _k not in ('infile', 'outfile', 'overwrite')
        ))
        for _font in pack
    )

    with monobit.open_location(outfile, 'w', overwrite=args.overwrite) as (outstream, outcontainer):
        # get saver arguments
        saver = monobit.formats.savers.get_saver(outstream, format=args.to_)
        if saver:
            add_script_args(parser, saver)
        args = parser.parse_args()
        # convert arguments to type accepted by operation
        save_args = convert_args(args, saver)
        monobit.save(pack, outstream, where=outcontainer, format=args.to_, **save_args)
