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

scriptables = {}


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

    _scriptable_func.__annotations__.update(script_args or {})
    _scriptable_func = convert_arguments(_scriptable_func)
    if not wrapper:
        _scriptable_func = check_arguments(_scriptable_func)
    if record:
        _scriptable_func = record_history(_scriptable_func)
    _scriptable_func.pack_operation = pack_operation
    # register the scriptable function
    scriptables[_scriptable_func.__name__] = _scriptable_func
    return _scriptable_func


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
            if kwarg not in func.__annotations__:
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
            _type = func.__annotations__.get(kwarg, Any)
            converter = CONVERTERS.get(_type, _type)
            conv_kwargs[kwarg] = converter(value)
        # call wrapped function
        result = func(*args, **conv_kwargs)
        return result

    return _converted_func
