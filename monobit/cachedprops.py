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



class DefaultProps:
    """
    Namespace with recognised fields and defaults.
    Define field types (converters) and defaults in class definition.
    >>> class MyProps(DefaultProps)
    >>>    field_1: int
    >>>    field_2: int = 2
    >>> p = MyProps()
    >>> p.field_2
    >>> 2
    >>> p.field_1
    >>> 0
    where field_1 has an implied default, int() == 0
    """

    def __init__(self, _comments=None, **kwargs):
        # disable cacheing while building the object
        self._set_defaults()
        self._props = {}
        [
            setattr(self, _field, _value)
            for _field, _value in kwargs.items()
            #if not _field.startswith('_')
        ]
        _comments = _comments or {}
        self._comments = _comments
        # enable cacheing
        self._cache = {}

    def __repr__(self):
        return (
            type(self).__name__
            + '(\n    ' +
            '\n    '.join(
                f'{_k}={_v!r},' for _k, _v in self._props.items()
                if not _k.startswith('_')
            )
            + '\n)'
        )

    @classmethod
    def _set_defaults(cls):
        """If a type constructor is given in the annotations, use that to set the default."""
        # if a type constructor is given in the annotations, use that to set the default
        # note that we're changing the *class* namespace on the *instance* initialiser
        # which feels a bit hacky
        # but this will be a no-op after the first instance has initialised
        if not hasattr(cls, '_init'):
            # type's attributes - these are the calculated properties
            cls._attribs = list(vars(cls))
            try:
                start = cls._attribs.index('__properties_start__')
                end = cls._attribs.index('__properties_end__')
            except ValueError:
                pass
            else:
                # cut back the list, speeds up setattr
                cls._attribs = cls._attribs[start+1:end]
            cls._attribs = set(cls._attribs)
            # types, converters and default values for overriding/custom properties
            cls._types = {**cls.__annotations__}
            cls._converters = {
                _field: CONVERTERS.get(_type, _type)
                for _field, _type in cls._types.items()
            }
            cls._defaults = {
                # can't use .get() as _type() would fail for some defaulted fields
                _field: vars(cls)[_field] if _field in vars(cls) else _type()
                #CONVERTERS(_type, _type)()
                for _field, _type in cls.__annotations__.items()
                if _field not in cls._attribs
            }
            cls._init = True

    @classmethod
    def _get_default(cls, field):
        """Default value for a property."""
        return cls._defaults.get(field, None)

    def _defined(self, field):
        """Writable property has been explicitly set."""
        return self._props.get(field, None)

    @classmethod
    def _known(cls, field):
        """Field is a writable property."""
        # note that checked_properties are not included, writable_properties and regular fields are
        return field in cls._defaults or field in cls._attribs

    def __getattr__(self, field):
        if field.startswith('_'):
            raise AttributeError(field)
        try:
            return self._get_property(field)
        except KeyError as e:
            raise AttributeError(e)

    def _get_property(self, field):
        try:
            return self._props[field]
        except KeyError:
            pass
        return self._defaults[field]

    def __setattr__(self, field, value):
        if field.startswith('_'):
            return super().__setattr__(field, value)
        if field in self._attribs:
            self._cache = {}
            return super().__setattr__(field, value)
        return self._set_property(field, value)

    def _set_property(self, field, value):
        if value is None:
            self._props.pop(field, None)
        else:
            # this fails because not all our annotations are actual types
            #field_type = self._types.get(field, None)
            #if field_type and not isinstance(field, field_type):
            converter = self._converters.get(field, None)
            if converter:
                value = converter(value)
            self._props[field] = value
        self._cache = {}


def writable_property(arg=None, *, field=None):
    """Decorator to take property from property table, if defined; calculate otherwise."""
    if not callable(arg):
        return partial(writable_property, field=arg)
    fn = arg
    field = field or fn.__name__
    cached_fn = delayed_cache(fn)

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
        #logging.debug(f'Setting overridable property {field}={value}.')
        self._set_property(field, value)

    return property(_getter, _setter)


def checked_property(fn):
    """Non-overridable property, attempted writes will be logged and dropped."""
    field = fn.__name__

    _getter = delayed_cache(fn)

    @wraps(fn)
    def _setter(self, value):
        logging.info(f'Non-overridable property {field} cannot be set to {value}; ignored.')

    return property(_getter, _setter)


def delayed_cache(fn):
    """Cache only once _frozen attribute is set."""
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
