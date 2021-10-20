"""
monobit.scripting - scripting utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import os
import logging
from contextlib import contextmanager
from functools import wraps, partial


###################################################################################################
# mark functions for scripting
# annotations give converters from string to desired type
# docstings provide help text

def scriptable(*args, script_args=None, name=None, record=True):
    """Decorator to register operation for scripting."""
    if not args:
        # called as @scriptable(script_args=...)
        # return decorator with these arguments set as extra args
        return partial(scriptable, script_args=script_args, name=name, record=record)
    else:
        # called as @scriptable
        func, = args
        name = name or func.__name__
        script_args = script_args or {}
        script_args = {**script_args, **func.__annotations__}

        @wraps(func)
        def _scriptable_func(*args, **kwargs):
            result = func(*args, **kwargs)
            if record and result:
                history = _repr_script_args(name, kwargs, script_args)
                try:
                    result = tuple(_item.add_history(history) for _item in iter(result))
                except TypeError:
                    result = result.add_history(history)
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

def get_script_args(func, args):
    """Get arguments accepted by operation."""
    if not func:
        return {}
    return {
        _name: _arg
        for _name, _arg in vars(args).items()
        if _arg is not None and _name in func.script_args
    }

def add_script_args(parser, func):
    """Add scriptable function arguments to argparser."""
    if not func:
        return
    for arg, _type in func.script_args.items():
        if _type == bool:
            parser.add_argument('--' + arg.strip('_'), dest=arg, action='store_true')
            parser.add_argument('--no-' + arg.strip('_'), dest=arg, action='store_false')
        else:
            parser.add_argument('--' + arg.strip('_'), dest=arg, type=_type)


def _repr_script_args(operation_name, arg_dict, script_args):
    """Represent converter parameters."""
    return (
        operation_name.replace('_', '-') + ' '
        + ' '.join(
            f'--{_k}={_v}'
            for _k, _v in arg_dict.items()
            # exclude unset and non-operation parameters
            if _v and _k in script_args
        )
    ).strip()


###################################################################################################
# script type converters

def tuple_int(pairstr):
    """Convert NxNx... or N,N,... to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

rgb = tuple_int
pair = tuple_int


###################################################################################################
# frame for main scripts

@contextmanager
def main(args, loglevel=logging.WARNING):
    """Main script context."""
    if not hasattr(args, 'debug'):
        args.debug = True
    if args.debug:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s')
    try:
        yield
    except BrokenPipeError:
        # happens e.g. when piping to `head`
        # https://stackoverflow.com/questions/16314321/suppressing-printout-of-exception-ignored-message-in-python-3
        sys.stdout = os.fdopen(1)
    except Exception as exc:
        logging.error(exc)
        if not hasattr(args, 'debug') or args.debug:
            raise
