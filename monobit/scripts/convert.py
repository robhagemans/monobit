"""
Apply operation to bitmap font
(c) 2019--2023 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
from types import SimpleNamespace as Namespace
from pathlib import Path

import monobit
from monobit.scripting import (
    wrap_main, parse_subcommands, print_help, argrecord, GLOBAL_ARG_PREFIX
)

script_name = Path(sys.argv[0]).name

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
    f'usage: {script_name} '
    + '[INFILE] [LOAD-OPTIONS] '
    + ' '.join(f'[{GLOBAL_ARG_PREFIX}{_op}]' for _op in global_options)
    + ' [COMMAND [OPTION...]] ...'
    + ' [to [OUTFILE] [SAVE-OPTIONS]]'
)

def _get_context_help(rec):
    if rec.args:
        file = rec.args[0]
    else:
        file = rec.kwargs.get('infile', '')
    format = rec.kwargs.get('format', '')
    if rec.command == 'load':
        func, *_ = monobit.loaders.get_for(format=format)
    else:
        func, *_ = monobit.savers.get_for(format=format)
    if func:
        return func.script_args
    return None

def help(command_args):
    """Print the usage help message."""
    context_help = {
        _rec.command: _get_context_help(_rec)
        for _rec in command_args
        if _rec.command in ('load', 'save', 'to')
    }
    context_help = {_k: _v for _k, _v in context_help.items() if _v}
    print_help(command_args, usage, operations, global_options, context_help)

def version():
    """Print the version string."""
    print(f'monobit v{monobit.__version__}')


def main():
    command_args, global_args = parse_subcommands(operations, global_options=global_options)
    debug = 'debug' in global_args.kwargs
    with wrap_main(debug):
        if 'help' in global_args.kwargs:
            help(command_args)

        elif 'version' in global_args.kwargs:
            version()

        else:
            # ensure first command is load
            if not command_args[0].command and (
                    command_args[0].args or command_args[0].kwargs
                    or len(command_args) == 1 or command_args[1].command != 'load'
                ):
                command_args[0].command = 'load'
                command_args[0].func = operations['load']
                # special case `convert infile outfile` for convenience
                if len(command_args[0].args) == 2:
                    command_args.append(argrecord(
                        command='save', func=operations['save'],
                        args=[command_args[0].args.pop()])
                    )
            # ensure last command is save
            if command_args[-1].command not in ('to', 'save'):
                command_args.append(argrecord(command='save', func=operations['save']))

            fonts = []
            for args in command_args:
                if not args.command:
                    continue
                logging.debug('Executing command `%s`', args.command)
                operation = operations[args.command]
                if operation == monobit.load:
                    fonts += operation(*args.args, **args.kwargs)
                elif operation.pack_operation:
                    fonts = operation(fonts, *args.args, **args.kwargs)
                else:
                    fonts = tuple(
                        operation(_font, *args.args, **args.kwargs)
                        for _font in fonts
                    )

if __name__ == '__main__':
    main()
