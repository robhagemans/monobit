"""
monobit.encoding.charmaps.charmapclass - character maps

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import unicodedata
from pathlib import Path
from html.parser import HTMLParser
from importlib.resources import files
from functools import cached_property

from ...binary import align
from ...labels import Codepoint, Char, to_label, to_labels
from ...unicode import is_printable, is_fullwidth, unicode_name
from ..base import Encoder, normalise_name, NotFoundError
from .. import tables


class Charmap(Encoder):
    """Convert between unicode and ordinals using stored mapping."""

    # charmap file format parameters
    _formats = {}

    def __init__(self, mapping=None, *, name='', _late_load=False):
        """Create charmap from a dictionary codepoint -> char."""
        super().__init__(normalise_name(name))
        if not _late_load:
            if not mapping:
                mapping = {}
                name = ''
            # copy dict
            self._init_ord2chr = {**mapping}

    @cached_property
    def _ord2chr(self):
        try:
            return self._init_ord2chr
        except AttributeError:
            return self._build_mapping()

    @cached_property
    def _chr2ord(self):
        return {_v: _k for _k, _v in self._ord2chr.items()}

    @classmethod
    def register_loader(cls, format, **default_kwargs):
        """Decorator to register charmap reader."""
        def decorator(reader):
            cls._formats[format] = (reader, default_kwargs)
            return reader
        return decorator

    @classmethod
    def load(cls, filename, *, format=None, name='', **kwargs):
        """Lazily create new charmap from file."""
        if not name:
            name = Path(filename).stem
        self = cls(name=normalise_name(name), _late_load=True)
        filename = str(filename)
        # inputs that look like explicit paths used directly
        # otherwise it's relative to the tables package
        if filename.startswith('/') or filename.startswith('.'):
            path = Path(filename)
        else:
            path = files(tables) / filename
        if not path.exists():
            raise NotFoundError(f'Charmap file `{filename}` does not exist')
        format = format or path.suffix[1:].lower()
        try:
            reader, format_kwargs = cls._formats[format]
        except KeyError as exc:
            raise NotFoundError(f'Undefined charmap file format {format}.') from exc
        self._load_reader = reader
        self._load_path = path
        self._load_kwargs = {**format_kwargs, **kwargs}
        return self

    def _build_mapping(self):
        """Create new charmap from file."""
        try:
            data = self._load_path.read_bytes()
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load charmap file `{str(self._load_path)}`: {exc}')
        if not data:
            raise NotFoundError(f'No data in charmap file `{str(self._load_path)}`.')
        mapping = self._load_reader(data, **self._load_kwargs)
        return mapping

    def char(self, *labels):
        """Convert codepoint sequence to character, return empty string if missing."""
        for label in labels:
            codepoint = to_label(label)
            if isinstance(codepoint, bytes):
                try:
                    return Char(self._ord2chr[codepoint])
                except KeyError as e:
                    return Char('')

    def codepoint(self, *labels):
        """Convert character to codepoint sequence, return empty tuple if missing."""
        for label in labels:
            char = to_label(label)
            if isinstance(char, str):
                try:
                    return Codepoint(self._chr2ord[char])
                except KeyError as e:
                    return Codepoint()

    @property
    def mapping(self):
        return {**self._ord2chr}

    def __len__(self):
        """Number of defined codepoints."""
        return len(self._ord2chr)

    def __eq__(self, other):
        """Compare to other Charmap."""
        return isinstance(other, Charmap) and (self._ord2chr == other._ord2chr)

    # charmap operations

    def __sub__(self, other):
        """Return encoding with only characters that differ from right-hand side."""
        return Charmap(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if other.char(_k) != _v},
            name=f'[{self.name}]-[{other.name}]'
        )

    def __or__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        mapping = {**self.mapping}
        mapping.update(other.mapping)
        return Charmap(mapping=mapping, name=f'{self.name}')

    def distance(self, other):
        """Return number of different code points."""
        other_only = set(other._ord2chr) - set(self._ord2chr)
        self_only = set(self._ord2chr) - set(other._ord2chr)
        different = set(
            _k for _k, _v in self._ord2chr.items()
            if _k in other._ord2chr and other.char(_k) != _v
        )
        return len(different) + len(other_only) + len(self_only)

    def subset(self, codepoint_range):
        """Return encoding only for given range of codepoints."""
        return Charmap(
            mapping={
                _k: _v
                for _k, _v in self._ord2chr.items()
                if (_k in codepoint_range) or (len(_k) == 1 and _k[0] in codepoint_range)
            },
            name=f'subset[{self.name}]'
        )

    def overlay(self, other, codepoint_range):
        """Return encoding overlaid with all characters in the overlay range taken from rhs."""
        return self | other.subset(codepoint_range)

    def shift(self, by=0x80):
        """
        Increment all codepoints by the given amount.

        by: amount to increment
        """
        return Charmap(
            mapping={
                bytes(Codepoint(int(Codepoint(_k))+by)): _v
                for _k, _v in self._ord2chr.items()
            },
            name=f'shift-{by:x}[{self.name}]'
        )


    # representations

    def chart(self, page=0):
        """Chart of page in charmap."""
        bg = '\u2591'
        cps = range(256)
        cps = (((page, _c) if page else (_c,)) for _c in cps)
        chars = (self.char(_cp) for _cp in cps)
        chars = ((_c if is_printable(_c) else '\ufffd') for _c in chars)
        chars = ((_c if is_fullwidth(_c) else ((_c + ' ') if _c else bg*2)) for _c in chars)
        # deal with Nonspacing Marks while keeping table format
        chars = ((' ' +_c if unicodedata.category(_c[:1]) == 'Mn' else _c) for _c in chars)
        chars = [*chars]
        return ''.join((
            '    ', ' '.join(f'_{_c:x}' for _c in range(16)), '\n',
            '  +', '-'*48, '-', '\n',
            '\n'.join(
                ''.join((f'{_r:x}_|', bg, bg.join(chars[16*_r:16*(_r+1)]), bg))
                for _r in range(16)
            )
        ))

    def table(self):
        """Mapping table"""
        return '\n'.join(
            f'0x{_k.hex()}: u+{ord(_v):04X}  # {unicode_name(_v)}' for _k, _v in self._ord2chr.items()
        )

    def __repr__(self):
        """Representation."""
        if self._ord2chr:
            mapping = f'<{len(self._ord2chr)} code points>'
            chart = f'\n{self.chart()}\n'
            return (
                f"{type(self).__name__}(name='{self.name}', mapping={mapping}){chart}"
            )
        return (
            f"{type(self).__name__}()"
        )


class Unicode(Encoder):
    """Convert between unicode and UTF-32 ordinals."""

    def __init__(self):
        """Unicode converter."""
        super().__init__('unicode')

    @staticmethod
    def char(*labels):
        """Convert codepoint to character."""
        for label in labels:
            codepoint = to_label(label)
            if isinstance(codepoint, bytes):
                # ensure codepoint length is a multiple of 4
                codepoint = codepoint.rjust(align(len(codepoint), 2), b'\0')
                # convert as utf-32 chunks
                chars = tuple(
                    chr(int.from_bytes(codepoint[_start:_start+4], 'big'))
                    for _start in range(0, len(codepoint), 4)
                )
                try:
                    return Char(''.join(chars))
                except ValueError:
                    return Char('')

    @staticmethod
    def codepoint(*labels):
        """Convert character to codepoint."""
        for label in labels:
            char = to_label(label)
            if isinstance(char, str):
                # we used to normalise to NFC here, presumably to reduce multi-codepoint situations
                # but it leads to inconsistency between char and codepoint for canonically equivalent chars
                #char = unicodedata.normalize('NFC', char)
                return Codepoint(b''.join(ord(_c).to_bytes(4, 'big') for _c in char))
        return Codepoint()

    def __repr__(self):
        """Representation."""
        return type(self).__name__ + '()'
