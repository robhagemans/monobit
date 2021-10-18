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
    return {
        _name: _func
        for _name, _func in cls.__dict__.items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


###################################################################################################
# script type converters

def boolean(boolstr):
    """Convert str to bool."""
    return boolstr.lower() == 'true'

def _tuple(pairstr):
    """Convert NxNx... or N,N,... to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

rgb = _tuple
pair = _tuple


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
