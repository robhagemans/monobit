#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args

SCRIPT = 'modify'


###################################################################################################
# argument parsing

# split argument list in command components
def command_argv(command_words):
    part_argv = []
    for arg in sys.argv[1:]:
        if arg in command_words and part_argv:
            yield part_argv
            part_argv = []
        part_argv.append(arg)
    yield part_argv


commands = []

for cargv in command_argv(('load', 'save', *monobit.operations)):

    # parse command line
    parser = argparse.ArgumentParser(
        usage=f'{SCRIPT} [--debug] [--help] <command> [command-options] [ ... ]',
        formatter_class=argparse.MetavarTypeHelpFormatter,
    )

    #parser.add_argument(
    #    '--overwrite', action='store_true',
    #    help='overwrite existing output file'
    #)
    parser.add_argument(
        '--debug', action='store_true',
        help='show debugging output'
    )

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
        group = add_script_args(sub, func.script_args, name=name)
        sub.add_argument(
            '-h', '--help', action='store_true',
            help=argparse.SUPPRESS
        )
        subs[name] = sub


    # force error on unknown arguments
    args = parser.parse_args(cargv)

    if args.help:
        subs[args.operation].print_help()
        sys.exit(0)

    # find out which operation we're asked to perform
    operation = monobit.operations[args.operation]

    commands.append((operation, args))


debug = any(_args.debug for _, _args in commands)


with main(debug, logging.WARNING):

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
