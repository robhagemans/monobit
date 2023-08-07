"""
monobit.plumbing.scripting - scripting utilities

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import wraps, partial

from ..base import Any, passthrough, to_int, CONVERTERS, NOT_SET
from .history import record_history


class ArgumentError(TypeError):
    """Invalid keyword argument."""

    def __init__(self, func, arg):
        super().__init__(f'{arg} is an invalid keyword for {func}')


###############################################################################
# mark functions for scripting
# annotations give converters from string to desired type
# docstings provide help text

def scriptable(
        *args, script_args=None,
        record=True, pack_operation=False, wrapper=False,
    ):
    """
    Decorator to register operation for scripting.

    Decorated functions get
    - a script_args record for argument parsing
    - automatic type conversion
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
    # called as @scriptable
    func, = args

    @wraps(func)
    def _scriptable_func(*args, **kwargs):
        return func(*args, **kwargs)

    script_args = ScriptArgs(func, extra_args=script_args or {})
    _scriptable_func.script_args = script_args
    _scriptable_func = convert_arguments(_scriptable_func)
    if not wrapper:
        _scriptable_func.script_args = script_args
        _scriptable_func = check_arguments(_scriptable_func)
    if record:
        _scriptable_func.script_args = script_args
        _scriptable_func = record_history(_scriptable_func)
    _scriptable_func.script_args = script_args
    _scriptable_func.pack_operation = pack_operation
    return _scriptable_func


def get_scriptables(cls):
    """Get dict of functions marked as scriptable."""
    return {
        _name: _func
        for _cls in (cls, *cls.__bases__)
        for _name, _func in vars(_cls).items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


def check_arguments(func):
    """Check if arguments to function are in the registered script args."""

    @wraps(func)
    def _checked_func(*args, **kwargs):
        # rename argument provided with dashes
        kwargs = {
            _kwarg.replace('-', '_'): _value
            for _kwarg, _value in kwargs.items()
        }
        for kwarg in kwargs:
            if kwarg not in func.script_args:
                raise ArgumentError(func.__name__, kwarg) from None
        # call wrapped function
        return func(*args, **kwargs)

    return _checked_func


def convert_arguments(func):
    """Convert given arguments to the type in registered script args."""

    @wraps(func)
    def _converted_func(*args, **kwargs):
        # apply converters to argument
        conv_kwargs = {}
        for kwarg, value in kwargs.items():
            # skip not-specified arguments
            if value is NOT_SET:
                continue
            _type = func.script_args.get(kwarg, Any)
            converter = CONVERTERS.get(_type, _type)
            conv_kwargs[kwarg] = converter(value)
        # call wrapped function
        result = func(*args, **conv_kwargs)
        return result

    return _converted_func


###############################################################################
# argument parsing

class ScriptArgs:
    """Record of script arguments."""

    def __init__(
            self, func=None, *, extra_args=None,
        ):
        """Extract script name, arguments and docs."""
        self._script_args = {}
        if func:
            self._script_args.update(func.__annotations__)
        self._script_args.update(extra_args or {})

    def items(self):
        """Iterate over argument, type pairs."""
        return self._script_args.items()

    def get(self, arg, default):
        return self._script_args.get(arg, default)

    def __iter__(self):
        """Iterate over arguments."""
        return iter(self._script_args)

    def __getitem__(self, arg):
        return self._script_args[arg]

    def __contains__(self, arg):
        return arg in self._script_args
