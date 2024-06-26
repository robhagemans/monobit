"""
monobit.plumbing.args - script argument parser

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import sys
import logging
from types import SimpleNamespace
from contextlib import contextmanager

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
            # rename argument provided with dashes
            ns.kwargs = {
                _kwarg.replace('-', '_'): _value
                for _kwarg, _value in ns.kwargs.items()
            }
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
