#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args, convert_script_args, repr_script_args


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

# find out which operation we're asked to perform
args, _ = parser.parse_known_args()

# help screen should include loader/saver arguments if from/to specified
if args.help:
    if args.from_:
        loader = monobit.loaders.get_for(format=args.from_)
        add_script_args(parser, loader)
    if args.to_:
        saver = monobit.savers.get_for(format=args.to_)
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
        loader = monobit.loaders.get_for(instream, format=args.from_, do_open=True)
        add_script_args(parser, loader)
        # don't raise if no loader - it may be a container we can extract
        args, _ = parser.parse_known_args()
        # convert arguments to type accepted by operation
        load_args = convert_script_args(loader, vars(args))
        pack = monobit.load(instream, where=incontainer, format=args.from_, **load_args)

    # set encoding
    if args.encoding:
        pack = tuple(_font.set_encoding(args.encoding) for _font in pack)
    # add comments
    if args.comments:
        with open(args.comments) as f:
            pack = tuple(_font.add_comments(f.read()) for _font in pack)

    # record converter parameters
    pack = tuple(
        _font.set_properties(
            converter_parameters=repr_script_args(
                'convert', vars(args), loader, 'encoding', 'comments'
            )
        )
        for _font in pack
    )

    with monobit.open_location(outfile, 'w', overwrite=args.overwrite) as (outstream, outcontainer):
        # get saver arguments
        saver = monobit.savers.get_for(outstream, format=args.to_)
        add_script_args(parser, saver)
        args = parser.parse_args()
        # convert arguments to type accepted by operation
        save_args = convert_script_args(saver, vars(args))
        monobit.save(pack, outstream, where=outcontainer, format=args.to_, **save_args)
