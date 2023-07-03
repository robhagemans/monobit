"""
monobit.cachedprops - defaultable, cached property sets with type conversion

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


import logging
from types import SimpleNamespace
from functools import partial, wraps, cache
from itertools import chain
from textwrap import indent, wrap

from .basetypes import CONVERTERS
from .properties import Props


class HasProps:

    _defaults = {}
    _converters = {}

    def __init__(self):
        self._cache = {}
        self._props = {}

    def __repr__(self):
        return (
            type(self).__name__
            + '(\n    ' +
            '\n    '.join(
                f'{_k}={_v!r},'
                for _k, _v in self._props.items()
            )
            + '\n)'
        )

    def _get_property(self, field):
        try:
            return self._props[field]
        except KeyError:
            return type(self)._defaults[field]

    def __getattr__(self, field):
        if not field.startswith('_'):
            try:
                return self._get_property(field)
            except KeyError:
                pass
        raise AttributeError(field)

    @staticmethod
    def get_converters(typeclass):
        # types, converters and default values for overriding/custom properties
        return {
            _field: CONVERTERS.get(_type, _type)
            for _field, _type in typeclass.__annotations__.items()
        }

    def _set_property(self, field, value):
        if value is None:
            self._props.pop(field, None)
        else:
            try:
                converter = type(self)._converters[field]
                value = converter(value)
            except KeyError:
                pass
            assert value is not None
            self._props[field] = value

    def _set_properties(self, props):
        converters = tuple(type(self)._converters.get(_f, None) for _f in props)
        self._props = {
            _k: _conv(_v) if _conv else _v
            for (_k, _v), _conv in zip(props.items(), converters)
            if _v is not None and (
                not hasattr(type(self), _k)
                # fset does not exist (not a property) or equals None (not settable)
                or getattr(getattr(type(self), _k), 'fset', None) is not None
            )
        }
        assert None not in self._props.values()

    def get_properties(self):
        return {**self._props}

    def get_property(self, key):
        """Get value for property."""
        try:
            return self._get_property(key)
        except KeyError:
            return None

    def get_defined(self, key):
        return self._props.get(key, None)

    @classmethod
    def get_default(cls, field):
        return cls._defaults.get(field, None)

    @classmethod
    def is_known_property(cls, field):
        return field in cls._converters


###############################################################################
# cached and overridable properties

def writable_property(fn):
    """Decorator to take property from property table, if defined; calculate otherwise."""
    field = fn.__name__
    cached_fn = cached(fn)

    @wraps(fn)
    def _getter(self):
        try:
            # only use if explicitly set on the instance
            return self._props[field]
        except KeyError:
            pass
        return cached_fn(self)

    @wraps(fn)
    def _setter(self, value):
        self._props[field] = value

    return property(_getter, _setter)


def checked_property(fn):
    """Non-overridable cached property."""
    _getter = cached(fn)
    return property(_getter)


def cached(fn):
    field = fn.__name__

    @wraps(fn)
    def _getter(self):
        try:
            return self._cache[field]
        except KeyError:
            pass
        value = fn(self)
        self._cache[field] = value
        return value

    return _getter
