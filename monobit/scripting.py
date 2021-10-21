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
        script_args = ScriptArgs(name, **script_args, **func.__annotations__)

        @wraps(func)
        def _scriptable_func(*args, **kwargs):
            result = func(*args, **kwargs)
            if record and result:
                history = script_args.to_str(kwargs)
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

class ScriptArgs():
    """Record of script arguments."""

    def __init__(self, *args, **script_args):
        """Script name and arguments."""
        if args:
            self.name = args[0]
        else:
            self.name = ''
        self._script_args = script_args or {}

    def pick(self, arg_namespace):
        """Get arguments accepted by operation."""
        return {
            _name: _arg
            for _name, _arg in vars(arg_namespace).items()
            if _arg is not None and _name in self._script_args
        }

    def to_str(self, arg_dict):
        """Represent converter parameters."""
        return (
            self.name.replace('_', '-') + ' '
            + ' '.join(
                f'{_k}={_v}'
                for _k, _v in arg_dict.items()
                # exclude unset and non-operation parameters
                if _v and _k in self._script_args
            )
        ).strip()

    def __iter__(self):
        """Iterate over argument, type pairs."""
        return iter(self._script_args.items())


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
