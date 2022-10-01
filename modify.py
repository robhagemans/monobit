#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, add_script_args, split_argv, parse_converter_args


SCRIPT = 'modify'

all_operations = {
    'load': monobit.load,
    'save': monobit.save,
    **monobit.operations
}


###################################################################################################
# argument parsing

def build_parser():

    # global options

    parser = argparse.ArgumentParser(
        add_help=False, conflict_handler='resolve',
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
    for name, func in all_operations.items():
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


# ensure we load & save
if command_argv and not args.help:
    if command_argv[0][:1] != ['load']:
        command_argv = [['load']] + command_argv
    if command_argv[-1][:1] != ['save']:
        command_argv = command_argv + [['save']]



# parse command args
commands = []
for cargv in command_argv:
    parser, subs = build_parser()
    command_args, _ = parser.parse_known_args(cargv)

    if command_args.operation == 'load':
        load_args, _ = parser.parse_known_args(cargv)
        loader = monobit.loaders.get_for_location(load_args.infile, format=load_args.format)
        kwargs = parse_converter_args(subs['load'], loader, cargv)
    elif command_args.operation == 'save':
        save_args, _ = parser.parse_known_args(cargv)
        saver = monobit.savers.get_for_location(save_args.outfile, format=save_args.format, do_open=False)
        kwargs = parse_converter_args(subs['save'], saver, cargv)
    else:
        command_args = parser.parse_args(cargv)
        kwargs= {}
    # find out which operation we're asked to perform
    operation = all_operations[command_args.operation]
    kwargs.update(operation.script_args.pick(command_args))
    commands.append((operation, kwargs))

    if args.help:
        subs[command_args.operation].print_help()
        sys.exit(0)

if args.help:
    parser.print_help()
    sys.exit(0)


###################################################################################################
# main operation

with main(args.debug):
    fonts = []
    for operation, args in commands:
        if operation == all_operations['load']:
            fonts = operation(**args)
        else:
            fonts = tuple(
                operation(_font, **args)
                for _font in fonts
            )
