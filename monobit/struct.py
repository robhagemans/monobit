"""
monobit.struct - property structures

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import ctypes
import struct
from ctypes import sizeof

import logging
from types import SimpleNamespace
from functools import partial, wraps
from itertools import chain
try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()


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
        return '\n'.join(f'{_k}: {_v}' for _k, _v in vars(self).items())

    def __repr__(self):
        return (
            type(self).__name__
            + '(\n    ' +
            '\n    '.join(f'{_k}={_v!r},' for _k, _v in vars(self).items())
            + '\n)'
        )


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

    def __init__(self, *args, **kwargs):
        # disable cacheing while building the object
        self._frozen = False
        super().__init__(*args)
        # if a type constructor is given in the annotations, use that to set the default
        # note that we're changing the *class* namespace on the *instance* initialiser
        # which feels a bit hacky
        # but this will be a no-op after the first instance has initialised
        self._set_defaults()
        # use Props.__setitem__ for value conversion
        # we use None to *unset* properties
        for field, value in kwargs.items():
            if value is not None:
                field = normalise_property(field)
                setattr(self, field, value)
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
        try:
            calc_value = fn(self)
        except AttributeError:
            pass
        else:
            if value == calc_value:
                logging.debug(f'Overridable property {field}={value} consistently set.')
            else:
                logging.info(f'Setting overridable property {field}={value} (was {calc_value}).')
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
        try:
            calc_value = fn(self)
        except Exception as e:
            logging.warning(f'Could not check value of {field}: {e}')
        if value == calc_value:
            logging.debug(f'Non-overridable property {field}={value} consistently set.')
        else:
            logging.warning(
                f'Non-overridable property {field}={calc_value} cannot be set to {value}.'
            )

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



##############################################################################
# binary structs

# base types
char = ctypes.c_char
uint8 = ctypes.c_uint8
int8 = ctypes.c_int8
uint16 = ctypes.c_uint16
int16 = ctypes.c_int16
uint32 = ctypes.c_uint32
int32 = ctypes.c_int32


# type strings
TYPES = {
    'byte': uint8,
    'ubyte': uint8,
    'uint8': uint8,
    'B': uint8,

    'int8': int8,
    'b': int8,

    'word': uint16,
    'uword': uint16,
    'uint16': uint16,
    'H': uint16,

    'short': int16,
    'int16': int16,
    'h': int16,

    'dword': uint32,
    'uint32': uint32,
    'I': uint32,
    'L': uint32,

    'long': int32,
    'int32': int32,
    'i': int32,
    'l': int32,

    'char': char,
    's': char,
}


class bitfield:
    """Pair (type, bit_width) to describe bit field."""

    def __init__(self, fieldtype, bits):
        """Pair (type, bit_width) to describe bit field."""
        self.type = fieldtype
        self.bits = bits

flag = bitfield('B', 1)

def _parse_type(atype):
    """Convert struct member type specification to ctypes base type or array."""
    if isinstance(atype, bitfield):
        return (*_parse_type(atype.type), atype.bits)
    if isinstance(atype, type):
        return atype,
    try:
        return TYPES[atype],
    except KeyError:
        pass
    if isinstance(atype, str) and atype.endswith('s'):
        return char * int(atype[:-1]),
    raise ValueError('Field type `{}` not understood'.format(atype))


def _build_struct(parent, **description):
    """Use friendly keyword description to build ctypes struct subclass that supports vars()."""
    fields = tuple(
        (_field, *_parse_type(_type))
        for _field, _type in description.items()
    )
    return _define_struct(parent, fields)


def _define_struct(parent, fields):
    """Build ctypes struct subclass with fields list provided."""

    class Struct(parent):
        """Struct with binary representation."""
        _fields_ = fields
        _pack_ = True

        def __repr__(self):
            """String representation."""
            props = vars(self)
            return type(self).__name__ + '({})'.format(
                ', '.join(
                    '{}={}'.format(_fld, _val)
                    for _fld, _val in props.items()
                )
            )

        @property
        def __dict__(self):
            """Extract the fields dictionary."""
            return dict(
                (field, getattr(self, field))
                for field, *_ in self._fields_
            )

        def __add__(self, other):
            """Concatenate structs."""
            addedstruct = _define_struct(parent, self._fields_ + other._fields_)
            return addedstruct(**vars(self), **vars(other))

        def __getattribute__(self, attr):
            """Convert attributes where still necessary."""
            value = super().__getattribute__(attr)
            if isinstance(value, ctypes.Array):
                return tuple(value)
            return value

    return _wrap_struct(Struct)

def _wrap_struct(cstruct):
    """Wrap ctypes structs/struct arrays with convenience methods."""
    cstruct.size = ctypes.sizeof(cstruct)
    cstruct.array = lambda n: _wrap_struct(cstruct * n)
    cstruct.read_from = lambda stream: cstruct.from_buffer_copy(stream.read(ctypes.sizeof(cstruct)))
    cstruct.from_bytes = cstruct.from_buffer_copy
    return cstruct

def _wrap_base_type(ctyp, parent):
    """Wrap ctypes base types with convenience methods."""
    # while struct members defined as ctypes resolve to Python types,
    # base ctypes are objects that are not compatible with Python types
    # so we wrap the base type in a one-member struct
    cls = _build_struct(parent, value=ctyp)
    cls.array = lambda n: _wrap_base_type(ctyp * n, parent)
    cls.read_from = lambda stream: cls.from_buffer_copy(stream.read(ctypes.sizeof(ctyp))).value
    cls.from_bytes = lambda *args: cls.from_buffer_copy(*args).value
    return cls


# interface:
#
# >>> mystruct = big_endian.Struct(one=uint8, two=int32)
# >>> record = mystruct.from_bytes(b'\0\1\2\3\4')
# >>> record
# Struct(one=0, two=16909060)
# >>> hex(record.two)
# '0x1020304'
#
# >>> mystruct = little_endian.Struct(one=uint8, two=int32)
# >>> record = mystruct.from_bytes(b'\0\1\2\3\4')
# >>> hex(record.two)
# '0x4030201'

# note that uint8 etc. are base types while BE.uint8 etc are wrapped
# we can't use the latter in a struct definition

def _binary_types(parent):
    return SimpleNamespace(
        Struct=partial(_build_struct, parent),
        char=_wrap_base_type(char, parent),
        uint8=_wrap_base_type(uint8, parent),
        int8=_wrap_base_type(int8, parent),
        uint16=_wrap_base_type(uint16, parent),
        int16=_wrap_base_type(int16, parent),
        uint32=_wrap_base_type(uint32, parent),
        int32=_wrap_base_type(int32, parent),
    )

big_endian = _binary_types(ctypes.BigEndianStructure)
little_endian = _binary_types(ctypes.LittleEndianStructure)
