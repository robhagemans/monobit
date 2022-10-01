#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args, split_argv, parse_converter_args


###################################################################################################
# argument parsing

# split argument list in command components
first_argv, *last_argv = split_argv('to')
# drop 'to' command word
if last_argv:
    last_argv = last_argv[0][1:]


# parse command line
# global options
parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage='%(prog)s [--debug] [--help] [infile] [load-options] to [outfile] [save-options]'
)
parser.add_argument(
    '--debug', action='store_true', help='show debugging output'
)
parser.add_argument(
    '-h', '--help', action='store_true',
    help='show this help message and exit'
)

args, first_argv = parser.parse_known_args(first_argv)

if args.debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.WARNING
logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')


# load options

load_parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage=argparse.SUPPRESS
)
load_group = add_script_args(load_parser, monobit.load, positional=['infile'])
load_args, _ = load_parser.parse_known_args(first_argv)
loader = monobit.loaders.get_for_location(load_args.infile, format=load_args.format)
load_kwargs = parse_converter_args(load_parser, loader, first_argv)


# save options

save_parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage=argparse.SUPPRESS
)

save_group = add_script_args(save_parser, monobit.save, positional=['outfile'])
save_group.add_argument(
    '--encoding', default='', type=str,
    help='override encoding/codepage (default: infer from metadata in file)'
)
save_group.add_argument(
    '--comments', default='', type=str,
    help='add global comments from text file'
)

save_args, _ = save_parser.parse_known_args(last_argv)
saver = monobit.savers.get_for_location(save_args.outfile, format=save_args.format)
save_kwargs = parse_converter_args(save_parser, saver, last_argv)

if args.help:
    parser.print_help()
    print()
    load_parser.print_help()
    save_parser.print_help()
    sys.exit(0)

# force errors
load_parser.parse_args(first_argv)
save_parser.parse_args(last_argv)



###################################################################################################
# main operation

with main(args.debug):

    # if no infile or outfile provided, use stdio
    infile = load_args.infile or sys.stdin
    outfile = save_args.outfile or sys.stdout

    pack = monobit.load(infile, format=load_args.format, **load_kwargs)

    # set encoding
    if save_args.encoding:
        pack = tuple(_font.set(encoding=load_args.encoding) for _font in pack)
    # add comments
    if save_args.comments:
        with open(save_args.comments) as f:
            pack = tuple(_font.add(comments=f.read()) for _font in pack)

    monobit.save(pack, outfile, overwrite=save_args.overwrite, format=save_args.format, **save_kwargs)
