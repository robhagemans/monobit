"""
monobit.plumbing.history - records history of objects

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import shlex
from functools import wraps
from contextlib import contextmanager

from .args import ARG_PREFIX


_record = True

@contextmanager
def switch_off_recording():
    global _record
    # call wrapped function
    _record, save = False, _record
    yield
    _record = save


def record_history(func):
    """Ensure history gets recorded on a method call."""

    @wraps(func)
    def _recorded_func(*args, **kwargs):
        with switch_off_recording():
            result = func(*args, **kwargs)
        result = _update_history_tracker(result, func, *args, **kwargs)
        return result

    return _recorded_func


def no_record_history(func):
    """Switch off history recording."""

    @wraps(func)
    def _recorded_func(*args, **kwargs):
        with switch_off_recording():
            result = func(*args, **kwargs)
        return result

    return _recorded_func


def _update_history_tracker(result, func, *args, **kwargs):
    """Update history field in Font or Glyph."""
    global _record
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
