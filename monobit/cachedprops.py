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
from .properties import Props, normalise_property



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
        self._frozen = False
        self._set_defaults()
        self._props = {}
        [
            self._set_property(_field, _value)
            for _field, _value in kwargs.items()
            #if not _field.startswith('_')
        ]
        _comments = _comments or {}
        self._comments = {
            normalise_property(_k): _v
            for _k, _v in _comments.items()
        }
        # enable cacheing
        self._cache = {}
        self._frozen = True

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
            cls._init = True
            cls._types = {**cls.__annotations__}
            cls._defaults = {
                # can't use .get() as _type() would fail for some defaulted fields
                _field: vars(cls)[_field] if _field in vars(cls) else _type()
                #CONVERTERS(_type, _type()
                for _field, _type in cls.__annotations__.items()
            }

    @classmethod
    def _get_default(cls, field):
        """Default value for a property."""
        return cls._defaults.get(normalise_property(field), None)

    def _defined(self, field):
        """Writable property has been explicitly set."""
        return self._props.get(normalise_property(field), None)

    @classmethod
    def _known(cls, field):
        """Field is a writable property."""
        # note that checked_properties are not included, writable_properties and regular fields are
        return normalise_property(field) in cls._defaults

    def __getattr__(self, field):
        if field.startswith('_'):
            raise AttributeError(field)
        try:
            return self._props[field]
        except KeyError:
            pass
        try:
            return self._defaults[field]
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, field, value):
        if hasattr(self, '_frozen') and self._frozen and not field.startswith('_'):
            raise ValueError('Cannot set property on frozen object.')
        super().__setattr__(field, value)

    def _set_property(self, field, value):
        field = normalise_property(field)
        if value is None:
            self._props.pop(field, None)
        else:
            try:
                converter = self._types[field]
                converter = CONVERTERS.get(converter, converter)
            except KeyError:
                pass
            else:
                value = converter(value)
            self._props[field] = value

    def __iter__(self):
        """Iterate on default definition order first, then remaining keys."""
        have_defaults = (_k for _k in self._defaults)
        others = (_k for _k in self._props.keys() if _k not in self._defaults)
        return chain(have_defaults, others)


def writable_property(arg=None, *, field=None):
    """Decorator to take property from property table, if defined; calculate otherwise."""
    if not callable(arg):
        return partial(writable_property, field=arg)
    fn = arg
    field = field or fn.__name__
    field = normalise_property(field)
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
        if self._frozen:
            raise ValueError('Cannot set property on frozen object.')
        #logging.debug(f'Setting overridable property {field}={value}.')
        self._set_property(field, value)

    return property(_getter, _setter)


def checked_property(fn):
    """Non-overridable property, attempted writes will be logged and dropped."""
    field = normalise_property(fn.__name__)

    _getter = delayed_cache(fn)

    @wraps(fn)
    def _setter(self, value):
        if self._frozen:
            raise ValueError('Cannot set property on frozen object.')
        logging.info(f'Non-overridable property {field} cannot be set to {value}; ignored.')

    return property(_getter, _setter)


def as_tuple(arg=None, *, fields=None, tuple_type=None):
    """
    Decorator to take summarise multiple fields as a (settable) tuple.

    The decorated function is discarded except for the name, so use as:
    @as_tuple(('x', 'y'))
        def coord(): pass
    """
    if not callable(arg):
        return partial(as_tuple, fields=arg, tuple_type=tuple_type)
    fn = arg

    tuple_type = tuple_type or tuple

    @wraps(fn)
    def _getter(self):
        # in this case, always use the fields, whether defaulted or set
        return tuple_type(tuple(
            getattr(self, _field)
            for _field in fields
        ))

    @wraps(fn)
    def _setter(self, value):
        for field, element in zip(fields, tuple_type(value)):
            self._set_property(field, element)

    return property(_getter, _setter)



def delayed_cache(fn):
    """Cache only once _frozen attribute is set."""
    field = normalise_property(fn.__name__)

    @wraps(fn)
    def _getter(self):
        if not self._frozen:
            return fn(self)
        try:
            return self._cache[field]
        except KeyError:
            pass
        self._cache[field] = fn(self)
        return self._cache[field]

    return _getter
