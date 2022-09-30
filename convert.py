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
load_parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage='%(prog)s [infile] [load-options] to [outfile] [save-options]'
)
load_parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)

load_group = load_parser.add_argument_group('load-options')
load_group.add_argument('infile', nargs='?', type=str, default='', help=argparse.SUPPRESS)
load_group.add_argument(
    '--format', default='', type=str,
    help='input format (default: infer from magic number or filename)'
)
load_group.add_argument(
    '--encoding', default='', type=str,
    help='override encoding/codepage (default: infer from metadata in file)'
)

load_args, _ = load_parser.parse_known_args(first_argv)

loader_script_args = monobit.loaders.get_args(format=load_args.format)
add_script_args(load_parser, loader_script_args, name='load', format=load_args.format)


# to ensure loader / saver arguments are included in help
# we should only parse it after adding those
load_parser.add_argument(
    '-h', '--help', action='store_true',
    help='show this help message and exit'
)

load_args, _ = load_parser.parse_known_args(first_argv)



save_parser = argparse.ArgumentParser(
    add_help=False, conflict_handler='resolve',
    formatter_class=argparse.MetavarTypeHelpFormatter,
    usage=argparse.SUPPRESS
)
save_parser.add_argument(
    '--debug', action='store_true',
    help=argparse.SUPPRESS
)

save_group = save_parser.add_argument_group('save-options')
save_group.add_argument('outfile', nargs='?', type=str, default='', help=argparse.SUPPRESS)
save_group.add_argument(
    '--format', default='', type=str,
    help='output format (default: infer from filename)'
)
save_group.add_argument(
    '--comments', default='', type=str,
    help='add global comments from text file'
)
save_group.add_argument(
    '--overwrite', action='store_true',
    help='overwrite existing output file'
)

save_args, _ = save_parser.parse_known_args(last_argv)


saver_script_args = monobit.savers.get_args(format=save_args.format)
add_script_args(save_parser, saver_script_args, name='save', format=save_args.format)

# to ensure loader / saver arguments are included in help
# we should only parse it after adding those
save_parser.add_argument(
    '-h', '--help', action='store_true',
    help=argparse.SUPPRESS
)

save_args, _ = save_parser.parse_known_args(last_argv)

if load_args.help or save_args.help:
    load_parser.print_help()
    save_parser.print_help()
    sys.exit(0)

# force errors
load_parser.parse_args(first_argv)
save_parser.parse_args(last_argv)



###################################################################################################
# main operation

with main(load_args.debug or save_args.debug, logging.INFO):

    # if no infile or outfile provided, use stdio
    infile = load_args.infile or sys.stdin
    outfile = save_args.outfile or sys.stdout

    pack = monobit.load(infile, format=load_args.format, **loader_script_args.pick(load_args))

    # set encoding
    if load_args.encoding:
        pack = tuple(_font.set(encoding=load_args.encoding) for _font in pack)
    # add comments
    if save_args.comments:
        with open(save_args.comments) as f:
            pack = tuple(_font.add(comments=f.read()) for _font in pack)

    monobit.save(pack, outfile, overwrite=save_args.overwrite, format=save_args.format, **saver_script_args.pick(save_args))
