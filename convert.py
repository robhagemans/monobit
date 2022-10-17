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
from monobit.scripting import main, parse_subcommands, print_option_help


all_operations = {
    'load': monobit.load,
    'save': monobit.save,
    'to': monobit.save,
    **monobit.operations
}

GLOBAL_FLAGS = {
    'help': (bool, 'Print a help message and exit.'),
    'version': (bool, 'Show monobit version and exit.'),
    'debug': (bool, 'Enable debugging output.'),
}

command_args, global_args = parse_subcommands(all_operations, global_options=GLOBAL_FLAGS)

debug = 'debug' in global_args.kwargs
if debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.WARNING
logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')


# only global kwargs or nothing preceding a load command
if len(command_args) > 1 and (
        command_args[0].command == command_args[1].command == 'load'
        and not command_args[0].args and not command_args[0].kwargs
    ):
    logging.debug('Dropping empty first command followed by `load`')
    command_args.pop(0)

for number, args in enumerate(command_args):
    logging.debug(
        'Command #%d: %s %s %s',
        number,
        args.command,
        ' '.join(args.args),
        ' '.join(f'--{_k}={_v}' for _k, _v in args.kwargs.items())
    )

logging.debug(
    'Global args: %s %s',
    ' '.join(global_args.args),
    ' '.join(f'--{_k}={_v}' for _k, _v in global_args.kwargs.items())
)


HELP_TAB = 25

if 'help' in global_args.kwargs:
    print(
        f'usage: {Path(__file__).name} '
        + '[INFILE] '
        + ' '.join(f'[--{_op}]' for _op in GLOBAL_FLAGS)
        + ' [COMMAND [OPTION...]] ...'
        + ' [to OUTFILE]'
    )
    print()
    print('Options')
    print('=======')
    print()
    for name, (vartype, doc) in GLOBAL_FLAGS.items():
        print_option_help(name, vartype, doc, HELP_TAB, add_unsetter=False)


    print()
    print('Commands and their options')
    print('==========================')
    print()
    for op, func in all_operations.items():
        if op == 'to':
            continue
        print(f'{op} '.ljust(HELP_TAB-1, '-') + f' {func.script_args.doc}')
        for name, vartype in func.script_args._script_args.items():
            doc = func.script_args._script_docs.get(name, '').strip()
            print_option_help(name, vartype, doc, HELP_TAB)
        print()
        if op == 'load' and op in sys.argv[1:]:
            infile = sys.argv[sys.argv.index('load')+1]
            func = monobit.loaders.get_for_location(infile) #format=load_args.format
            for name, vartype in func.script_args._script_args.items():
                doc = func.script_args._script_docs.get(name, '').strip()
                print_option_help(name, vartype, doc, HELP_TAB)
            print()

elif 'version' in global_args.kwargs:
    print(f'monobit v{monobit.__version__}')

else:
    with main(debug):

        ###################################################################################################
        # main operation

        fonts = []
        for args in command_args:
            operation = all_operations[args.command]
            if operation == monobit.load:
                fonts += operation(*args.args, **args.kwargs)
            elif operation == monobit.save:
                operation(fonts, *args.args, **args.kwargs)
            else:
                fonts = tuple(
                    operation(_font, *args.args, **args.kwargs)
                    for _font in fonts
                )

