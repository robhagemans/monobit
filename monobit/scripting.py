"""
monobit.scripting - scripting utilities

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import os
import logging
import shlex
from contextlib import contextmanager
from functools import wraps, partial
from types import SimpleNamespace

from .basetypes import Any, passthrough, to_int, CONVERTERS


class ArgumentError(TypeError):
    """Invalid keyword argument."""

    def __init__(self, func, arg):
        super().__init__(f'{arg} is an invalid keyword for {func}')


###############################################################################
# mark functions for scripting
# annotations give converters from string to desired type
# docstings provide help text

_record = True

def scriptable(
        *args, script_args=None,
        record=True, pack_operation=False, wrapper=False,
    ):
    """
    Decorator to register operation for scripting.

    Decorated functions get
    - a script_args record for argument parsing
    - automatic type conversion
    - application of a font operation to all elements in a pack (unless pack_operation is set)
    - recorded history

    script_args: additional arguments not given in annotations
    record: record in history log
    pack_operation: function works on sequence of fonts
    wrapper: enable keyword argument passthrough
    """
    if not args:
        # called as @scriptable(script_args=...)
        # return decorator with these arguments set as extra args
        return partial(
            scriptable, script_args=script_args,
            record=record, pack_operation=pack_operation,
            wrapper=wrapper,
        )
    else:
        # called as @scriptable
        func, = args
        name = func.__name__
        script_args = script_args or {}
        script_args = ScriptArgs(func, name=name, extra_args=script_args)

        @wraps(func)
        def _scriptable_func(*args, **kwargs):
            global _record
            # apply converters to argument
            conv_kwargs = {}
            for kwarg, value in kwargs.items():
                kwarg = kwarg.replace('-', '_')
                # skip not-specified arguments
                if value is None:
                    continue
                try:
                    _type, _ = script_args[kwarg]
                except KeyError:
                    if not wrapper:
                        raise ArgumentError(name, kwarg) from None
                    _type = Any
                converter = CONVERTERS.get(_type, _type)
                conv_kwargs[kwarg] = converter(value)
            # call wrapped function
            _record, save = False, _record
            result = func(*args, **conv_kwargs)
            _record = save
            # update history tracker
            if record and _record and result and not 'history' in kwargs:
                history = script_args.get_history_item(*args, **kwargs)
                try:
                    result = tuple(
                        _item.append(history=history)
                        for _item in iter(result)
                    )
                except TypeError:
                    result = result.append(history=history)
            return result

        _scriptable_func.script_args = script_args
        _scriptable_func.pack_operation = pack_operation
        _scriptable_func.__name__ = name
        return _scriptable_func


def get_scriptables(cls):
    """Get dict of functions marked as scriptable."""
    return {
        _name: _func
        for _cls in (cls, *cls.__bases__)
        for _name, _func in vars(_cls).items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


###############################################################################
# argument parsing

class ScriptArgs:
    """Record of script arguments."""

    def __init__(
            self, func=None, *,
            name='', extra_args=None,
        ):
        """Extract script name, arguments and docs."""
        self.name = name
        self._script_args = {}
        self.doc = ''
        docs = ()
        if func:
            if func.__doc__:
                docs = func.__doc__.splitlines()
                docs = (_l.strip() for _l in docs)
            self.name = name or func.__name__
            self._script_args.update(func.__annotations__)
        self._script_args.update(extra_args or {})
        self._script_docs = {_k: '' for _k in self._script_args}
        self.doc = ''
        for line in docs:
            if not self.doc:
                self.doc = line
            if not line or ':' not in line:
                continue
            arg, doc = line.split(':', 1)
            if arg.strip() in self._script_args:
                self._script_docs[arg] = doc.strip()

    def get_history_item(self, *args, **kwargs):
        """Represent converter parameters."""
        return ' '.join(
            _e for _e in (
                self.name.replace('_', '-'),
                ' '.join(
                    f'{ARG_PREFIX}{_k.replace("_", "-")}={shlex.join((str(_v),))}'
                    for _k, _v in kwargs.items()
                    # exclude non-operation parameters
                    if _k.replace('-', '_') in self._script_args
                ),
            )
            if _e
        ).strip()

    def __iter__(self):
        """Iterate over argument, type, doc pairs."""
        return (
            (_arg,
            self._script_args[_arg],
            self._script_docs[_arg])
            for _arg in self._script_args
        )

    def __getitem__(self, arg):
        """Retrieve type, doc pair."""
        return (
            self._script_args[arg],
            self._script_docs[arg]
        )

    def __contains__(self, arg):
        return arg in self._script_args



###############################################################################
# argument parser

ARG_PREFIX = '-'
GLOBAL_ARG_PREFIX = '--'
FALSE_PREFIX = 'no-'

class IsSetFlag:
    """
    Represent a parameter that is set with no value,
    converts to True or empty string, not to other types.
    """
    def __bool__(self):
        return True
    def __repr__(self):
        return f'{type(self).__name__}()'
    def __str__(self):
        return ''

SET = IsSetFlag()


def argrecord(command='', func=None, args=None, kwargs=None):
    """Record holding arguments and options for one command."""
    return SimpleNamespace(command=command, func=func, args=args or [], kwargs=kwargs or {})


def parse_subcommands(operations, global_options):
    """Split argument list in command components and their options with values."""
    # global arguments - these get added here wherever they occur in the argv list
    global_ns = argrecord()
    command_args = []
    for subargv in _split_argv(*operations.keys()):
        command = ''
        if subargv and subargv[0] in operations:
            command = subargv.pop(0)
        command_ns = argrecord(command=command, func=operations.get(command, ''))
        expect_value = False
        for arg in subargv:
            if arg.startswith((ARG_PREFIX, GLOBAL_ARG_PREFIX)):
                if arg.startswith(GLOBAL_ARG_PREFIX):
                    key = arg[len(GLOBAL_ARG_PREFIX):]
                    key, _, value = key.partition('=')
                    # use -- for global args
                    #  try to interpret as local if there isn't one
                    if key in global_options:
                        ns = global_ns
                    else:
                        ns = command_ns
                elif arg.startswith(ARG_PREFIX):
                    key = arg[len(ARG_PREFIX):]
                    key, _, value = key.partition('=')
                    ns = command_ns
                # boolean flag prefixed with --no-
                if key.startswith(FALSE_PREFIX):
                    key = key[len(FALSE_PREFIX):]
                    ns.kwargs[key] = False
                    expect_value = False
                else:
                    # record the key as set even if still expecting a value
                    ns.kwargs[key] = value or SET
                    expect_value = value == ''
            elif expect_value:
                value = arg
                ns.kwargs[key] = value
                expect_value = False
            else:
                # positional argument
                ns = command_ns
                ns.args.append(arg)
        command_args.append(command_ns)
    return command_args, global_ns


def _split_argv(*command_words):
    """Split argument list in command components."""
    part_argv = []
    for arg in sys.argv[1:]:
        if arg in command_words:
            yield part_argv
            part_argv = []
        part_argv.append(arg)
    yield part_argv


# doc string alignment in usage text
HELP_TAB = 25

def _print_option_help(name, vartype, doc, tab, prefix, *, add_unsetter=True):
    if vartype == bool:
        print(f'{prefix}{name}\t{doc}'.expandtabs(tab))
        if add_unsetter:
            print(f'{prefix}{FALSE_PREFIX}{name}\tunset {prefix}{name}'.expandtabs(tab))
    else:
        print(f'{prefix}{name}=...\t{doc}'.expandtabs(tab))

def print_help(command_args, usage, operations, global_options, context_help):
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
            print(f'{op} '.ljust(HELP_TAB-1) + f' {func.script_args.doc}')
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
            print(f'{op} '.ljust(HELP_TAB-1, '-') + f' {func.script_args.doc}')
            for name, vartype, doc in func.script_args:
                _print_option_help(name, vartype, doc, HELP_TAB, ARG_PREFIX)
            print()
            if op in context_help:
                context_args = context_help[op]
                print(f'{context_args.name} '.ljust(HELP_TAB-1, '-') + f' {func.script_args.doc}')
                for name, vartype, doc in context_args:
                    _print_option_help(name, vartype, doc, HELP_TAB, ARG_PREFIX)
                print()



###############################################################################
# frame for main scripts

@contextmanager
def wrap_main(debug=False):
    """Main script context."""
    # set log level
    if debug:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.WARNING
    logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s', force=True)
    # run main script
    try:
        yield
    except BrokenPipeError:
        # happens e.g. when piping to `head`
        # https://stackoverflow.com/questions/16314321/suppressing-printout-of-exception-ignored-message-in-python-3
        sys.stdout = os.fdopen(1)
    except Exception as exc:
        logging.error(exc)
        if debug:
            raise
