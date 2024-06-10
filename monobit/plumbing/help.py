"""
monobit.plumbing.help - contextual help

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from ..storage.base import loaders, savers, wrappers, containers
from .args import GLOBAL_ARG_PREFIX, ARG_PREFIX, FALSE_PREFIX


# doc string alignment in usage text
HELP_TAB = 25


def get_argdoc(func, for_arg):
    """Get documentation for function argument."""
    if not func.__doc__:
        return ''
    for line in func.__doc__.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        arg, doc = line.split(':', 1)
        if arg.strip() == for_arg:
            return doc.strip()
    return ''


def get_funcdoc(func):
    """Get documentation for function."""
    if not func.__doc__:
        return ''
    for line in func.__doc__.splitlines():
        line = line.strip()
        if line:
            return line
    return ''


def _print_option_help(name, vartype, doc, tab, prefix, *, add_unsetter=True):
    name = name.replace('_', '-')
    if vartype == bool:
        print(f'{prefix}{name}\t{doc}'.expandtabs(tab))
        if add_unsetter:
            print(f'{prefix}{FALSE_PREFIX}{name}\tunset {prefix}{name}'.expandtabs(tab))
    else:
        print(f'{prefix}{name}=...\t{doc}'.expandtabs(tab))


def _print_with_bar(name, doc):
    print(f'{name} '.ljust(HELP_TAB-1, '-') + f' {doc}')


def _print_section(section_name, func):
    _print_with_bar(section_name, get_funcdoc(func))
    for name, vartype in func.__annotations__.items():
        doc = get_argdoc(func, name)
        _print_option_help(name, vartype, doc, HELP_TAB, ARG_PREFIX)
    print()



def print_help(command_args, usage, operations, global_options):
    print(usage)
    print()
    print('Options')
    print('=======')
    print()
    for name, (vartype, doc) in global_options.items():
        _print_option_help(name, vartype, doc, HELP_TAB, GLOBAL_ARG_PREFIX, add_unsetter=False)

    if not command_args or len(command_args) == 1 and not command_args[0].command:
        print()
        print('Commands')
        print('========')
        print()
        for op, func in operations.items():
            _print_with_bar(op, get_funcdoc(func))
    else:
        print()
        print('Commands and their options')
        print('==========================')
        print()
        for ns in command_args:
            op = ns.command
            if not op:
                continue
            func = ns.func
            _print_section(op, func)
            if op in ('load', 'save', 'to'):
                _print_context_help(**vars(ns))


def _print_context_help(command, args, kwargs, **ignore):
    format = kwargs.get('format', '')
    if command == 'load':
        func, *_ = loaders.get_for(format=format)
    else:
        func, *_ = savers.get_for(format=format)
    if func:
        _print_section(f'{command} -format={format}', func)
    container_format = kwargs.get('container_format', '')
    try:
        wrapper_classes = wrappers.get_for(format=container_format)
        func = wrapper_classes[0].__init__
    except (ValueError, IndexError) as e:
        print(e)
        pass
    else:
        _print_section(f'-container-format={container_format}', func)
    try:
        container_classes = containers.get_for(format=container_format)
        func = container_classes[0].__init__
    except (ValueError, IndexError) as e:
        print(e)
        pass
    else:
        _print_section(f'-container-format={container_format}', func)
