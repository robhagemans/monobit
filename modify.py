#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args, split_argv

SCRIPT = 'modify'


###################################################################################################
# argument parsing

def build_parser():
    # global options
    parser = argparse.ArgumentParser(
        add_help=False, conflict_handler='resolve',
        formatter_class=argparse.MetavarTypeHelpFormatter,
        usage='%(prog)s [--debug] [--help]  <command> [command-options] [ ... ]'
    )
    parser.add_argument(
        '--debug', action='store_true', help='show debugging output'
    )
    parser.add_argument(
        '-h', '--help', action='store_true',
        help='show this help message and exit'
    )

    # command options

    subparsers = parser.add_subparsers(
        dest='operation', 
        title='commands',
        prog=f'{SCRIPT} [--debug] [--help]',
    )
    subs = {}
    for name, func in monobit.operations.items():
        sub = subparsers.add_parser(
            name, help=func.script_args.doc, add_help=False,
            formatter_class=argparse.MetavarTypeHelpFormatter,
        )
        group = add_script_args(sub, func)
        subs[name] = sub

    return parser, subs


first_argv, *command_argv = split_argv('load', 'save', *monobit.operations)

parser, subs = build_parser()
args, first_argv = parser.parse_known_args(first_argv)

if args.debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.WARNING
logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')


# parse command args
commands = []
for cargv in command_argv:
    parser, subs = build_parser()
    command_args = parser.parse_args(cargv)
    # find out which operation we're asked to perform
    operation = monobit.operations[command_args.operation]
    commands.append((operation, command_args))

    if args.help:
        subs[command_args.operation].print_help()
        sys.exit(0)

if args.help:
    parser.print_help()
    sys.exit(0)




with main(args.debug):

    # load
    #fonts = monobit.load(args.infile or sys.stdin)
    fonts = monobit.load(sys.stdin)

    for operation, args in commands:

        # modify
        fonts = tuple(
            operation(_font, **operation.script_args.pick(args))
            for _font in fonts
        )

    # save
    #monobit.save(fonts, args.outfile or sys.stdout, overwrite=args.overwrite)
    monobit.save(fonts, sys.stdout)
