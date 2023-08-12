"""
monobit.plumbing.history - records history of objects

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import shlex
from functools import wraps

from .args import ARG_PREFIX


_record = True


def record_history(func):
    """Ensure history gets recorded on a method call."""

    @wraps(func)
    def _recorded_func(*args, **kwargs):
        global _record
        # call wrapped function
        _record, save = False, _record
        result = func(*args, **kwargs)
        _record = save
        # update history tracker
        if _record and result and not 'history' in kwargs:
            history = _get_history_item(func, *args, **kwargs)
            try:
                result = type(result)(
                    _item.append(history=history)
                    for _item in iter(result)
                )
            except TypeError:
                result = result.append(history=history)
        return result

    return _recorded_func


def _get_history_item(func, *args, **kwargs):
    """Represent converter parameters."""
    return ' '.join(
        _e for _e in (
            func.__name__.replace('_', '-'),
            ' '.join(
                f'{ARG_PREFIX}{_k.replace("_", "-")}={shlex.join((str(_v),))}'
                for _k, _v in kwargs.items()
                # exclude non-operation parameters
                if _k.replace('-', '_') in func.__annotations__
            ),
        )
        if _e
    ).strip()
