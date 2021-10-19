"""
monobit.scripting - scripting utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import os
import logging
from contextlib import contextmanager


###################################################################################################
# mark functions for scripting
# annotations give converters from string to desired type
# docstings provide help text

def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.script_args = fn.__annotations__
    return fn

def get_scriptables(cls):
    """Get dict of functions marked as scriptable."""
    return {
        _name: _func
        for _name, _func in cls.__dict__.items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


###################################################################################################
# argument parsing

def convert_script_args(operation, arg_dict):
    """Convert arguments to type accepted by operation, per annotation."""
    if not operation:
        return {}
    return {
        _name: _arg
        for _name, _arg in arg_dict.items()
        if _arg is not None and _name in operation.script_args
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


def repr_script_args(operation_name, arg_dict, operation, *include_args):
    """Record converter parameters."""
    return (
        operation_name.replace('_', '-') + ' '
        + ' '.join(
            f'--{_k}={_v}'
            for _k, _v in arg_dict.items()
            # exclude unset and non-operation parameters
            if _v and _k in tuple(operation.script_args) + tuple(include_args)
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
