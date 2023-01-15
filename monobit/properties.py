"""
monobit.properties - property structures

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


import logging
from types import SimpleNamespace
from functools import partial, wraps
from itertools import chain
from textwrap import indent, wrap
try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .basetypes import CONVERTERS


def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}


##############################################################################
# property sets

def extend_string(string, line):
    """Add a line to a multiline string."""
    return '\n'.join(
        _line
        for _line in string.split('\n') + [line]
        if _line
    )

def normalise_property(field):
    # preserve distinction between starting underscore (internal) and starting dash (user property)
    return field[:1] + field[1:].replace('-', '_')


class Props(SimpleNamespace):
    """
    SimpleNamespace with the dunder methods of a dict
    Not a mapping but allows both key-style and attribute-style access
    """

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

    def __getitem__(self, field):
        try:
            return getattr(self, normalise_property(field))
        except AttributeError as e:
            raise KeyError(field) from e

    def __setitem__(self, field, value):
        try:
            setattr(self, normalise_property(field), value)
        except AttributeError as e:
            raise KeyError(field) from e

    def __delitem__(self, field):
        try:
            delattr(self, normalise_property(field))
        except AttributeError as e:
            raise KeyError(field) from e

    def __len__(self):
        return len(vars(self))

    def __iter__(self):
        return iter(vars(self))

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


##############################################################################
# property sets with default values, override policy and type conversion


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


class DefaultProps(Props):
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

    # set to True when defaults have been set for a given type
    # on first instatntiation
    _init = False

    def __init__(self, *args, **kwargs):
        # disable cacheing while building the object
        self._frozen = False
        super().__init__(*args)
        # if a type constructor is given in the annotations, use that to set the default
        # note that we're changing the *class* namespace on the *instance* initialiser
        # which feels a bit hacky
        # but this will be a no-op after the first instance has initialised
        if not type(self)._init:
            self._set_defaults()
            type(self)._init = True
        # use Props.__setitem__ for value conversion
        # we use None to *unset* properties
        [
            setattr(self, normalise_property(field), value)
            for field, value in kwargs.items()
            if value is not None
        ]
        # enable cacheing
        self._cache = {}
        self._frozen = True

    def __repr__(self):
        return (
            type(self).__name__
            + '(\n    ' +
            '\n    '.join(
                f'{_k}={_v!r},' for _k, _v in vars(self).items()
                if not _k.startswith('_')
            )
            + '\n)'
        )

    def _set_defaults(self):
        """If a type constructor is given in the annotations, use that to set the default."""
        cls = type(self)
        for field, field_type in cls.__annotations__.items():
            if field not in vars(cls):
                setattr(cls, field, field_type())

    @classmethod
    def _get_default(cls, field):
        """Default value for a property."""
        return vars(cls).get(normalise_property(field), None)

    def _defined(self, field):
        """Writable property has been explicitly set."""
        return vars(self).get(normalise_property(field), None)

    @classmethod
    def _known(cls, field):
        """Field is a writable property."""
        # note that checked_properties are not included, writable_properties and regular fields are
        return normalise_property(field) in vars(cls)

    def __setattr__(self, field, value):
        if field != '_frozen' and self._frozen:
            raise ValueError('Cannot set property on frozen object.')
        try:
            converter = type(self).__annotations__[field]
            converter = CONVERTERS.get(converter, converter)
        except KeyError:
            pass
        else:
            value = converter(value)
        super().__setattr__(field, value)

    def __iter__(self):
        """Iterate on default definition order first, then remaining keys."""
        keys = vars(super()).keys()
        have_defaults = (_k for _k in type(self).__annotations__ if _k in keys)
        others = (_k for _k in keys if _k not in type(self).__annotations__)
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
            # get property through vars()
            # only use if explicitly set on the instance
            return vars(self)[field]
        except KeyError:
            pass
        return cached_fn(self)

    @wraps(fn)
    def _setter(self, value):
        if self._frozen:
            raise ValueError('Cannot set property on frozen object.')
        #logging.debug(f'Setting overridable property {field}={value}.')
        vars(self)[field] = value

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
            self[normalise_property(_field)]
            for _field in fields
        ))

    @wraps(fn)
    def _setter(self, value):
        for field, element in zip(fields, tuple_type(value)):
            self[normalise_property(field)] = element

    return property(_getter, _setter)
