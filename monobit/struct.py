"""
monobit.struct - binary structures

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import ctypes

import logging
from types import SimpleNamespace
from functools import partial


class StructError(ValueError):
    pass


##############################################################################
# binary structs


# type strings
TYPES = {
    'byte': ctypes.c_uint8,
    'ubyte': ctypes.c_uint8,
    'uint8': ctypes.c_uint8,
    'B': ctypes.c_uint8,

    'int8': ctypes.c_int8,
    'b': ctypes.c_int8,

    'word': ctypes.c_uint16,
    'uword': ctypes.c_uint16,
    'uint16': ctypes.c_uint16,
    'H': ctypes.c_uint16,

    'short': ctypes.c_int16,
    'int16': ctypes.c_int16,
    'h': ctypes.c_int16,

    'dword': ctypes.c_uint32,
    'uint32': ctypes.c_uint32,
    'I': ctypes.c_uint32,
    'L': ctypes.c_uint32,

    'long': ctypes.c_int32,
    'int32': ctypes.c_int32,
    'i': ctypes.c_int32,
    'l': ctypes.c_int32,

    'char': ctypes.c_char,
    's': ctypes.c_char,
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
    if isinstance(atype, _WrappedCType):
        return _parse_type(atype._ctype)
    if isinstance(atype, type):
        return atype,
    try:
        return TYPES[atype],
    except KeyError:
        pass
    if isinstance(atype, str) and atype.endswith('s'):
        return ctypes.c_char * int(atype[:-1]),
    raise ValueError('Field type `{}` not understood'.format(atype))


class _WrappedCValue:
    """Wrapper for ctypes value."""

    @classmethod
    def from_cvalue(cls, cvalue, type):
        obj = cls()
        obj._cvalue = cvalue
        obj._type = type
        return obj

    def __bytes__(self):
        return bytes(self._cvalue)


class _WrappedCType:
    """Wrapper for ctypes type, factory for _WrappedCValue objects."""

    def __mul__(self, count):
        """Create an array."""
        return self.array(count)

    __rmul__ = __mul__

    def __call__(self, *args, **kwargs):
        """Instantiate a struct variable."""
        # pylint: disable=no-member
        return self.from_cvalue(self._ctype(*args, **kwargs))

    def from_cvalue(self, cvalue):
        """Instantiate a struct variable from a cvalue."""
        # pylint: disable=no-member
        return self._value_cls.from_cvalue(cvalue, self)

    def from_bytes(self, *args):
        # pylint: disable=no-member
        try:
            cvalue = self._ctype.from_buffer_copy(*args)
        except ValueError as e:
            raise StructError(e) from e
        return self.from_cvalue(cvalue)

    def read_from(self, stream, offset=None):
        """Read struct from file."""
        if offset is not None:
            stream.seek(offset, 0)
        return self.from_bytes(stream.read(self.size))

    def array(self, count):
        return ArrayType(self, count)

    @property
    def size(self):
        # pylint: disable=no-member
        return ctypes.sizeof(self._ctype)



class ScalarValue(_WrappedCValue):
    """Wrapper for scalars."""

    def __repr__(self):
        return type(self).__name__ + '({})'.format(self._cvalue.value)

    def __add__(self, value):
        return self._cvalue.value + value

    __radd__ = __add__

    def __mul__(self, value):
        return self._cvalue.value * value

    __rmul__ = __mul__


class CharValue(ScalarValue):
    pass


class IntValue(ScalarValue):
    """Wrapper for integer scalars."""

    def __int__(self):
        return self._cvalue.value

    def __repr__(self):
        return type(self).__name__ + '({})'.format(self._cvalue.value)

    # the following allow this class to mostly stand in for an int
    # we should not aften need this as struct/array elements
    # come out as Pyton basetype int/bytes

    def __index__(self):
        return int(self)

    def __and__(self, rhs):
        return int(self) & rhs

    def __or__(self, rhs):
        return int(self) & rhs



class ScalarType(_WrappedCType):
    """Wrapper for scalar types. Mostly used to define arrays and structs."""

    def __init__(self, endian, ctype):
        if endian[:1].lower() in ('b', '>'):
            self._ctype = ctype.__ctype_be__
        elif endian[:1].lower() in ('l', '<'):
            self._ctype = ctype.__ctype_le__
        else:
            raise ValueError(f"Endianness '{endian}' not recognised.")
        if ctype == ctypes.c_char:
            self._value_cls = CharValue
        else:
            self._value_cls = IntValue


class StructValue(_WrappedCValue):
    """Wrapper for ctypes Structure."""

    def __getattr__(self, attr):
        if not attr.startswith('_'):
            value = getattr(self._cvalue, attr)
            if isinstance(value, (ctypes.Array, ctypes.Structure)):
                wrapper = self._type.element_types[attr]
                return wrapper.from_cvalue(value)
            return value
        raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if not attr.startswith('_'):
            # deal with StructValue objects
            try:
                value = value._cvalue
            except AttributeError:
                pass
            return setattr(self._cvalue, attr, value)
        return super().__setattr__(attr, value)

    def __delattr__(self, attr):
        if not attr.startswith('_'):
            return delattr(self._cvalue, attr)
        return super().__delattr__(attr)

    @property
    def __dict__(self):
        return dict(
            (field, getattr(self, field))
            for field, *_ in self._cvalue._fields_
        )

    def __repr__(self):
        props = vars(self)
        return type(self).__name__ + '({})'.format(
            ', '.join(
                '{}={}'.format(_fld, _val)
                for _fld, _val in props.items()
            )
        )


class StructType(_WrappedCType):
    """
    Represent a structured type.

    mystruct = StructType('big', first=uint8, second=uint16)
    s = mystruct(first=1, second=2)

    assert bytes(s) == b'\1\0\2'
    assert mystruct.from_bytes(b'\1\0\2') == s
    """

    _value_cls = StructValue

    def __init__(self, endian, /, **description):
        """Create a structured type."""
        if endian[:1].lower() in ('b', '>'):
            parent = ctypes.BigEndianStructure
        elif endian[:1].lower() in ('l', '<'):
            parent = ctypes.LittleEndianStructure
        else:
            raise ValueError(f"Endianness '{endian}' not recognised.")

        class _CStruct(parent):
            _fields_ = tuple(
                (_field, *_parse_type(_type))
                for _field, _type in description.items()
            )
            _pack_ = True

        self._ctype = _CStruct
        self.element_types = description

    def __call__(self, **kwargs):
        """Instantiate a struct variable."""
        kwargs = {
            _k: (_v._cvalue if isinstance(_v, _WrappedCValue) else _v)
            for _k, _v in kwargs.items()
        }
        return self.from_cvalue(self._ctype(**kwargs))


class ArrayValue(_WrappedCValue):
    """Wrapper for ctypes arrays."""

    def __getitem__(self, item):
        value = self._cvalue[item]
        if isinstance(value, (ctypes.Array, ctypes.Structure)):
            wrapper = self._type.element_type
            return wrapper.from_cvalue(value)
        return value

    def __iter__(self):
        return (self[_i] for _i in range(len(self)))

    def __len__(self):
        return len(self._cvalue)

    def __repr__(self):
        props = vars(self)
        return type(self).__name__ + '({})'.format(
            ', '.join(
                str(_s) for _s in iter(self)
            )
        )

class ArrayType(_WrappedCType):
    """Wrapper for ctypes array type."""

    _value_cls = ArrayValue

    def __init__(self, struct, count):
        self._count = count
        self.element_type = struct
        self._ctype = struct._ctype * count

    def __call__(self, *args):
        """Instantiate a struct variable."""
        if args and isinstance(args[0], _WrappedCValue):
            args = (_arg._cvalue for _arg in args)
        return ArrayValue.from_cvalue(self._ctype(*args), self)


def sizeof(wrapped):
    """Get size in bytes of a type or value."""
    if isinstance(wrapped, _WrappedCType):
        return wrapped.size
    return ctypes.sizeof(wrapped._cvalue)


big_endian = SimpleNamespace(
    Struct=partial(StructType, '>'),
    char=ScalarType('>', ctypes.c_char),
    uint8=ScalarType('>', ctypes.c_uint8),
    int8=ScalarType('>', ctypes.c_int8),
    uint16=ScalarType('>', ctypes.c_uint16),
    int16=ScalarType('>', ctypes.c_int16),
    uint32=ScalarType('>', ctypes.c_uint32),
    int32=ScalarType('>', ctypes.c_int32),
)

little_endian = SimpleNamespace(
    Struct=partial(StructType, '<'),
    char=ScalarType('<', ctypes.c_char),
    uint8=ScalarType('<', ctypes.c_uint8),
    int8=ScalarType('<', ctypes.c_int8),
    uint16=ScalarType('<', ctypes.c_uint16),
    int16=ScalarType('<', ctypes.c_int16),
    uint32=ScalarType('<', ctypes.c_uint32),
    int32=ScalarType('<', ctypes.c_int32),
)
