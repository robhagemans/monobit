"""
monobit.properties - property structures

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


import logging
from types import SimpleNamespace
from functools import partial, wraps, cache
from itertools import chain
from textwrap import indent, wrap

from .basetypes import CONVERTERS


def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}


def extend_string(string, line):
    """Add a line to a multiline string."""
    return '\n'.join(
        _line
        for _line in string.split('\n') + [line]
        if _line
    )


##############################################################################
# property sets

class Props(SimpleNamespace):
    """SimpleNamespace with additional methods"""

    # don't pollute the object namespace
    # we only have __dunder__ methods

    def __init__(self, *args, **kwargs):
        # convert from string representation
        if len(args) == 1 and isinstance(args[0], str):
            kwargs = dict(
                _line.strip().split(':', 1)
                for _line in args[0].splitlines()
            )
            args = ()
        super().__init__(*args, **kwargs)

    def __str__(self):
        strs = tuple(
            (str(_k), str(_v))
            for _k, _v in vars(self).items()
        )
        return '\n'.join(
            f'{_k}: ' + (indent('\n' + _v, '    ') if '\n' in _v else _v)
            for _k, _v in strs
        )

    def __repr__(self):
        return (
            type(self).__name__
            + '(\n' +
            indent(
                '\n'.join(f'{_k}={_v!r},' for _k, _v in vars(self).items()),
                '    '
            )
            + '\n)'
        )

    def __ior__(self, rhs):
        """Update with other Properties object."""
        self.__dict__.update(vars(rhs))
        return self

    def __or__(self, rhs):
        """Combine with other Properties object."""
        new = Props(**vars(self))
        new |= rhs
        return new

    def __isub__(self, rhs):
        """Remove a key, does not need to exist."""
        self.__dict__.pop(rhs, None)
        return self

    def __sub__(self, rhs):
        """Remove a key, does not need to exist."""
        new = Props(**vars(self))
        new -= rhs
        return new
