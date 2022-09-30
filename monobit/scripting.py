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
        script_args = ScriptArgs(func, name=name, extra_args=script_args)

        @wraps(func)
        def _scriptable_func(*args, **kwargs):
            result = func(*args, **kwargs)
            if record and result:
                history = script_args.to_str(kwargs)
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

    def __init__(self, func=None, *, name='', extra_args=None):
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
        self._script_docs = {_k: '' for _k in self._script_args}
        for line in docs:
            if not line or ':' not in line:
                continue
            arg, doc = line.split(':', 1)
            if arg.strip() in self._script_args:
                self._script_docs[arg] = doc
        self.doc = docs[0] if docs else ''

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
                # exclude non-operation parameters
                if _k in self._script_args
            )
        ).strip()

    def __iter__(self):
        """Iterate over argument, type pairs."""
        return (
            (_arg,
            self._script_args[_arg],
            self._script_docs[_arg])
            for _arg in self._script_args
        )


###################################################################################################
# script type converters

def tuple_int(pairstr):
    """Convert NxNx... or N,N,... to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

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


###################################################################################################


_CONVERTER = {
    int: any_int
}


def add_script_args(parser, script_args, *, name='', **kwargs):
    """Add scriptable function arguments to argparser."""
    if name:
        header = f'{name}-options'
        for key, value in kwargs.items():
            if value:
                header += f' for --{key}={value}'
        group = parser.add_argument_group(header)
    else:
        group = parser
    for arg, _type, doc in script_args:
        argname = arg.strip('_').replace('_', '-')
        if _type == bool:
            group.add_argument(f'--{argname}', dest=arg, help=doc, action='store_true')
            group.add_argument(
                f'--no-{argname}', dest=arg, help=f'unset --{argname}', action='store_false'
            )
        else:
            converter = _CONVERTER.get(_type, _type)
            group.add_argument(f'--{argname}', dest=arg, help=doc, type=converter)
    return group


###################################################################################################
# frame for main scripts

@contextmanager
def main(debug=False, loglevel=logging.WARNING):
    """Main script context."""
    if debug:
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
        if debug:
            raise
