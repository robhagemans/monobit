#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import logging

from types import SimpleNamespace as Namespace

import monobit
from monobit.scripting import main, split_argv


all_operations = {
    'load': monobit.load,
    'save': monobit.save,
    'to': monobit.save,
    **monobit.operations
}

ARG_PREFIX = '--'
FALSE_PREFIX = 'no-'

GLOBAL_FLAGS = {
    'help': (bool, 'Print a help messasge and exit.'),
    'debug': (bool, 'Enable debugging output.'),
}


command_argv = split_argv(*all_operations.keys())


global_kwargs = {}
global_args = []
command_args = []


for subargv in command_argv:
    # if no first command specified, use 'load'
    command = 'load'
    if subargv and subargv[0] in all_operations:
        command = subargv.pop(0)
    operation = all_operations[command]
    args = []
    kwargs = {}
    expect_value = False
    for arg in subargv:
        if arg.startswith(ARG_PREFIX):
            key = arg[len(ARG_PREFIX):]
            key, _, value = key.partition('=')
            expect_value = not bool(value)
            # boolean flag prefixed with --no-
            if key.startswith(FALSE_PREFIX):
                key = key[len(FALSE_PREFIX):]
                kwargs[key] = False
                expect_value = False
            else:
                try:
                    argtype, doc = GLOBAL_FLAGS[key]
                except KeyError:
                    pass
                else:
                    # being lazy here, I don't need anything but bools for now
                    assert argtype == bool
                    global_kwargs[key] = True
                    expect_value = False
                    continue
                try:
                    argtype, doc = operation.script_args[key]
                except KeyError:
                    pass
                else:
                    if argtype == bool:
                        kwargs[key] = True
                        expect_value = False
                # record the key even if still expecting a value, will default to empty
                kwargs[key] = value
        elif expect_value:
            value = arg
            kwargs[key] = value
        else:
            # positional argument
            args.append(arg)
    command_args.append(Namespace(
        command=command,
        args=args,
        kwargs=kwargs
    ))


debug = 'debug' in global_kwargs
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
    ' '.join(global_args),
    ' '.join(f'--{_k}={_v}' for _k, _v in global_kwargs.items())
)


def print_option_help(name, vartype, doc):
    if vartype == bool:
        print(f'{ARG_PREFIX}{name}\t{doc}'.expandtabs(20))
        print(f'{ARG_PREFIX}{FALSE_PREFIX}{name}\tunset {ARG_PREFIX}{name}'.expandtabs(20))
    else:
        print(f'{ARG_PREFIX}{name}: {vartype.__name__}\t{doc}'.expandtabs(20))


if 'help' in global_kwargs:
    for op, func in all_operations.items():
        if op == 'to':
            continue

        print(f'{op}\t{func.script_args.doc}'.expandtabs(20))
        for name, vartype in func.script_args._script_args.items():
            doc = func.script_args._script_docs.get(name, '').strip()
            print_option_help(name, vartype, doc)
        print()

        if op == 'load' and op in sys.argv[1:]:
            infile = sys.argv[sys.argv.index('load')+1]
            func = monobit.loaders.get_for_location(infile) #format=load_args.format
            for name, vartype in func.script_args._script_args.items():
                doc = func.script_args._script_docs.get(name, '').strip()
                print_option_help(name, vartype, doc)
            print()

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

