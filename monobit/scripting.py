"""
monobit.scripting - scripting utilities

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import os
import logging
from contextlib import contextmanager
from functools import wraps, partial
from types import SimpleNamespace as Namespace


class ArgumentError(TypeError):
    """Invalid keyword argument."""

    def __init__(self, func, arg):
        super().__init__(f'{arg} is an invalid keyword for {func}()')


###################################################################################################
# mark functions for scripting
# annotations give converters from string to desired type
# docstings provide help text

def scriptable(
        *args, script_args=None, name=None, record=True, history_values=None, unknown_args='raise'
    ):
    """Decorator to register operation for scripting."""
    if not args:
        # called as @scriptable(script_args=...)
        # return decorator with these arguments set as extra args
        return partial(
            scriptable, script_args=script_args,
            name=name, record=record, history_values=history_values, unknown_args=unknown_args
        )
    else:
        # called as @scriptable
        func, = args
        name = name or func.__name__
        script_args = script_args or {}
        script_args = ScriptArgs(func, name=name, extra_args=script_args, history_values=history_values)

        @wraps(func)
        def _scriptable_func(*args, _record=True, **kwargs):
            # apply converters to argument
            conv_kwargs = {}
            for kwarg, value in kwargs.items():
                # skip not-specified arguments
                if value is None:
                    continue
                try:
                    _type, _ = script_args[kwarg]
                except KeyError:
                    if unknown_args == 'drop':
                        continue
                    if unknown_args == 'passthrough':
                        pass
                    elif unknown_args == 'warn':
                        logging.warning(ArgumentError(name, kwarg))
                        continue
                    else:
                        raise ArgumentError(name, kwarg) from None
                    _type = Any
                converter = _CONVERTER.get(_type, _type)
                conv_kwargs[kwarg] = converter(value)
            # call wrapped function
            result = func(*args, **conv_kwargs)
            # update history tracker
            if record and _record and result:
                history = script_args.to_str(conv_kwargs)
                try:
                    result = tuple(_item.add(history=history) for _item in iter(result))
                except TypeError:
                    result = result.add(history=history)
            return result

        _scriptable_func.script_args = script_args
        _scriptable_func.__name__ = name
        return _scriptable_func


def get_scriptables(cls):
    """Get dict of functions marked as scriptable."""
    return {
        _name: _func
        for _name, _func in cls.__dict__.items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


###################################################################################################
# argument parsing

class ScriptArgs():
    """Record of script arguments."""

    def __init__(self, func=None, *, name='', extra_args=None, history_values=None):
        """Extract script name, arguments and docs."""
        self.name = name
        self._script_args = {}
        self.doc = ''
        docs = ()
        if func:
            if func.__doc__:
                docs = [_l.strip() for _l in func.__doc__.split('\n') if _l.strip()]
            self.name = name or func.__name__
            self._script_args.update(func.__annotations__)
        self._script_args.update(extra_args or {})
        self._history_values = history_values or {}
        self._script_docs = {_k: '' for _k in self._script_args}
        for line in docs:
            if not line or ':' not in line:
                continue
            arg, doc = line.split(':', 1)
            if arg.strip() in self._script_args:
                self._script_docs[arg] = doc
        self.doc = docs[0] if docs else ''

    def to_str(self, arg_dict):
        """Represent converter parameters."""
        return (
            self.name.replace('_', '-')
            + ' ' + ' '.join(
                f'{_k}={_v}'
                for _k, _v in self._history_values.items()
            )
            + ' ' + ' '.join(
                f'{_k}={_v}'
                for _k, _v in arg_dict.items()
                # exclude non-operation parameters
                if _k in self._script_args
            )
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


###################################################################################################
# script type converters

def tuple_int(tup):
    """Convert NxNx... or N,N,... to tuple."""
    if isinstance(tup, str):
        return tuple(int(_s) for _s in tup.replace('x', ',').split(','))
    return tuple([*tup])

rgb = tuple_int
pair = tuple_int

def any_int(int_str):
    """Int-like or string in any representation."""
    try:
        # '0xFF' - hex
        # '0o77' - octal
        # '99' - decimal
        return int(int_str, 0)
    except (TypeError, ValueError):
        # '099' - ValueError above, OK as decimal
        # non-string inputs: TypeError, may be OK if int(x) works
        return int(int_str)


def Any(var):
    """Passthrough type."""
    return var


_CONVERTER = {
    int: any_int
}


###################################################################################################
# argument parser

ARG_PREFIX = '--'
FALSE_PREFIX = 'no-'


def _split_argv(*command_words):
    """Split argument list in command components."""
    part_argv = []
    for arg in sys.argv[1:]:
        if arg in command_words:
            yield part_argv
            part_argv = []
        part_argv.append(arg)
    yield part_argv


def parse_subcommands(commands, global_options):
    """Split argument list in command components and their options."""
    # global arguments - these get added here wherever they occur in the argv list
    global_args = Namespace(
        command='',
        args=[],
        kwargs={},
    )
    command_args = []
    for subargv in _split_argv(*commands):
        # if no first command specified, use 'load'
        command = 'load'
        if subargv and subargv[0] in commands:
            command = subargv.pop(0)
        operation = commands[command]
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
                        argtype, doc = global_options[key]
                    except KeyError:
                        pass
                    else:
                        # being lazy here, I don't need anything global but bools for now
                        assert argtype == bool
                        global_args.kwargs[key] = True
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
    return command_args, global_args


def print_option_help(name, vartype, doc, tab, add_unsetter=True):
    if vartype == bool:
        print(f'{ARG_PREFIX}{name}\t{doc}'.expandtabs(tab))
        if add_unsetter:
            print(f'{ARG_PREFIX}{FALSE_PREFIX}{name}\tunset {ARG_PREFIX}{name}'.expandtabs(tab))
    else:
        print(f'{ARG_PREFIX}{name}=...\t{doc}'.expandtabs(tab))


###################################################################################################
# frame for main scripts

@contextmanager
def main(debug=False):
    """Main script context."""
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
