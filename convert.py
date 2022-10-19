#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
from types import SimpleNamespace as Namespace
from pathlib import Path

import monobit
from monobit.scripting import main, parse_subcommands, print_option_help, argrecord


operations = {
    'load': monobit.load,
    'save': monobit.save,
    'to': monobit.save,
    **monobit.operations
}

global_options = {
    'help': (bool, 'Print a help message and exit.'),
    'version': (bool, 'Show monobit version and exit.'),
    'debug': (bool, 'Enable debugging output.'),
}

usage = (
    f'usage: {Path(__file__).name} '
    + '[INFILE] [LOAD-OPTIONS] '
    + ' '.join(f'[--{_op}]' for _op in global_options)
    + ' [COMMAND [OPTION...]] ...'
    + ' [to [OUTFILE] [SAVE_OPTIONS]]'
)


HELP_TAB = 25

def print_help(usage, command_args, global_options, context_help):
    print(usage)
    print()
    print('Options')
    print('=======')
    print()
    for name, (vartype, doc) in global_options.items():
        print_option_help(name, vartype, doc, HELP_TAB, add_unsetter=False)

    print()
    print('Commands and their options')
    print('==========================')
    print()
    for ns in command_args:
        op = ns.command
        if not op:
            continue
        func = operations[op]
        print(f'{op} '.ljust(HELP_TAB-1, '-') + f' {func.script_args.doc}')
        for name, vartype, doc in func.script_args:
            #doc = func.script_args._script_docs.get(name, '').strip()
            print_option_help(name, vartype, doc, HELP_TAB)
        print()
        if op in context_help:
            context_args = context_help[op]
            # print(f'options for `{op} {file}' + (f' --format={format}' if format else '') + '`')
            print(f'{context_args.name} '.ljust(HELP_TAB-1, '-') + f' {func.script_args.doc}')
            for name, vartype, doc in context_args:
                #doc = func.script_args._script_docs.get(name, '').strip()
                print_option_help(name, vartype, doc, HELP_TAB)
            print()


def get_context_help(rec):
    if rec.args:
        file = rec.args[0]
    else:
        file = rec.kwargs.get('infile', '')
    format = rec.kwargs.get('format', '')
    if rec.command == 'load':
        func = monobit.loaders.get_for_location(file, format=format)
    else:
        func = monobit.savers.get_for_location(file, format=format, do_open=False)
    return func.script_args


command_args, global_args = parse_subcommands(operations, global_options=global_options)
debug = 'debug' in global_args.kwargs

with main(debug):
    assert len(command_args) > 0
    # ensure first command is load
    if not command_args[0].command and (
            command_args[0].args or command_args[0].kwargs
            or command_args[1].command != 'load'
        ):
        command_args[0].command = 'load'
    # ensure last command is save
    if command_args[-1].command not in ('to', 'save'):
        command_args.append(argrecord(command='save'))

    if 'help' in global_args.kwargs:
        context_help = {
            _rec.command: get_context_help(_rec)
            for _rec in command_args
            if _rec.command in ('load', 'save', 'to')
        }
        print_help(usage, command_args, global_options, context_help)

    elif 'version' in global_args.kwargs:
        print(f'monobit v{monobit.__version__}')

    else:
        fonts = []
        for args in command_args:
            if not args.command:
                continue
            logging.debug('Executing command `%s`', args.command)
            operation = operations[args.command]
            if operation == monobit.load:
                fonts += operation(*args.args, **args.kwargs)
            elif operation == monobit.save:
                operation(fonts, *args.args, **args.kwargs)
            else:
                fonts = tuple(
                    operation(_font, *args.args, **args.kwargs)
                    for _font in fonts
                )

