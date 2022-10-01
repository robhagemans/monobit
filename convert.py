#!/usr/bin/env python3
"""
Extract bitmap font and save in different format
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args


###################################################################################################
# argument parsing

# split argument list in command components
is_saver_arg = False
first_argv, last_argv = [], []
for arg in sys.argv[1:]:
    if arg == 'to':
        is_saver_arg = True
        continue
    if is_saver_arg:
        last_argv.append(arg)
    else:
        first_argv.append(arg)

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
load_group = add_script_args(load_parser, monobit.load.script_args, name='load')
load_group.add_argument('infile', nargs='?', type=str, default='', help=argparse.SUPPRESS)
load_group.add_argument(
    '--encoding', default='', type=str,
    help='override encoding/codepage (default: infer from metadata in file)'
)

load_args, _ = load_parser.parse_known_args(first_argv)
loader = monobit.get_loader(load_args.infile, format=load_args.format)
if loader:
    add_script_args(load_parser, loader.script_args, name='load', format=load_args.format)
    load_args, _ = load_parser.parse_known_args(first_argv)
    load_kwargs = loader.script_args.pick(load_args)
else:
    load_kwargs = {}


# save options

save_parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage=argparse.SUPPRESS
)

save_group = add_script_args(save_parser, monobit.save.script_args, name='save')

save_group.add_argument('outfile', nargs='?', type=str, default='', help=argparse.SUPPRESS)
save_group.add_argument(
    '--comments', default='', type=str,
    help='add global comments from text file'
)

save_args, _ = save_parser.parse_known_args(last_argv)
saver = monobit.get_saver(save_args.outfile, format=save_args.format)
if saver:
    add_script_args(save_parser, saver.script_args, name='save', format=save_args.format)
    save_args, _ = save_parser.parse_known_args(last_argv)
    save_kwargs = saver.script_args.pick(save_args)
else:
    save_kwargs = {}


if args.help:
    parser.print_help()
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
    if load_args.encoding:
        pack = tuple(_font.set(encoding=load_args.encoding) for _font in pack)
    # add comments
    if save_args.comments:
        with open(save_args.comments) as f:
            pack = tuple(_font.add(comments=f.read()) for _font in pack)

    monobit.save(pack, outfile, overwrite=save_args.overwrite, format=save_args.format, **save_kwargs)
