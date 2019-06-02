"""
monobit.font - representation of font

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from functools import wraps
from typing import NamedTuple
import numbers
import logging
import pkgutil
import unicodedata

from .base import scriptable
from .glyph import Glyph


def number(value=0):
    """Convert to int or float."""
    if isinstance(value, str):
        value = float(value)
        if value == int(value):
            value = int(value)
    if not isinstance(value, numbers.Real):
        raise ValueError("Can't convert `{}` to number.".format(value))
    return value


class Label:
    """Glyph label."""

    def __init__(self, value):
        """Convert to int/unicode label as appropriate."""
        if isinstance(value, Label):
            self._value = value._value
            return
        if isinstance(value, (int, float)):
            self._value = int(value)
            return
        try:
            # check for ordinal (anything convertible to int)
            self._value = int(value, 0)
            return
        except ValueError:
            pass
        try:
            # accept decimals with leading zeros
            self._value = int(value.lstrip('0'))
            return
        except ValueError:
            pass
        # see if it counts as unicode label
        if value.lower().startswith('u+'):
            try:
                int(value[2:], 16)
            except ValueError as e:
                raise ValueError("'{}' is not a valid unicode label.".format(value)) from e
        # 'namespace' labels with a dot are not converted to lowercase
        if '.' in value:
            self._value = value
        else:
            self._value = value.lower()

    def __int__(self):
        """Convert to int if ordinal."""
        if self.is_ordinal:
            return self._value
        raise TypeError("Label is not an ordinal.")

    def __repr__(self):
        """Convert label to str."""
        if self.is_ordinal:
            return '0x{:02x}'.format(self._value)
        return self._value

    def __eq__(self, other):
        try:
            return self._value == other._value
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self._value)

    @property
    def is_unicode(self):
        return isinstance(self._value, str) and self._value.startswith('u+')

    @property
    def is_ordinal(self):
        return isinstance(self._value, int)

    @property
    def unicode(self):
        if self.is_unicode:
            return chr(int(self._value[2:], 16))
        return ''

    @property
    def unicode_name(self):
        if self.is_unicode:
            try:
                return unicodedata.name(self.unicode)
            except ValueError:
                pass
        return ''


class Coord(NamedTuple):
    """Coordinate tuple."""
    x: int
    y: int

    def __str__(self):
        return '{} {}'.format(self.x, self.y)

    @classmethod
    def create(cls, coord=0):
        if isinstance(coord, numbers.Real):
            return cls(coord, coord)
        if isinstance(coord, str):
            splits = coord.split(' ')
            if len(splits) == 1:
                return cls(number(splits[0]), number(splits[0]))
            elif len(splits) == 2:
                return cls(number(splits[0]), number(splits[1]))
        if isinstance(coord, tuple):
            if len(coord) == 2:
                return cls(number(coord[0]), number(coord[1]))
        raise ValueError("Can't convert `{}` to coordinate pair.".format(coord))


# recognised yaff properties and converters from str
# this also defines the default order in yaff files
PROPERTIES = {
    # font metadata
    'name': str, # full human name
    'foundry': str, # author or issuer
    'copyright': str, # copyright string
    'notice': str, # e.g. license string
    'revision': str, # font version
    'device': str, # target device name

    # descriptive:
    'point-size': number, # nominal point size
    'pixel-size': int, # nominal pixel size
    'dpi': Coord.create, # target resolution in dots per inch
    'family': str, # typeface/font family
    'weight': str, # normal, bold, light, etc.
    'slant': str, # roman, italic, oblique, etc
    'setwidth': str, # normal, condensed, expanded, etc.
    'style': str, # serif, sans, etc.
    'decoration': str, # underline, strikethrough, etc.

    # these can be determined from the bitmaps
    'spacing': str, # proportional, monospace, cell
    'x-width': int, # ink width of lowercase x (in proportional font)
    'average-width': number, # average ink width, rounded to tenths
    'bounding-box': Coord.create, # maximum ink width/height

    # positioning relative to origin:
    'direction': str, # left-to-right, right-to-left
    'offset': int, # transverse offset: bottom line of matrix relative to baseline
    'bearing-before': int, # horizontal offset from origin to matrix start
    'bearing-after': int, # horizontal offset from matrix end to next origin

    # other metrics (may affect interline spacing):
    'ascent': int, # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent': int, # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'leading': int, # vertical leading, defined as (pixels between baselines) - (pixel height)
    'x-height': int, # height of lowercase x relative to baseline
    'cap-height': int, # height of capital relative to baseline

    # character set:
    'encoding': str,
    'default-char': Label, # use question mark to replace missing glyph
    'word-boundary': Label, # word-break character (usually space)

    # conversion metadata:
    'converter': str,
    'source-name': str,
    'source-format': str,
}


class Codec:
    """Convert between unicode and ordinals using python codec."""

    def __init__(self, encoding):
        """Set up codec."""
        # force early LookupError if not known
        b'x'.decode(encoding)
        'x'.encode(encoding)
        self._encoding = encoding

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode label."""
        byte = bytes([int(ordinal)])
        unicode = byte.decode(self._encoding)
        return 'u+{:04x}'.format(ord(unicode))

    def unicode_to_ord(self, key, errors='strict'):
        """Convert ordinal to unicode label."""
        uniord = int(str(key)[2:], 16)
        unicode = chr(uniord)
        byte = unicode.encode(self._encoding, errors=errors)
        if not byte:
            # happens for errors='ignore'
            return ' '.encode(self._encoding)[0]
        return byte[0]


class Codepage:
    """Convert between unicode and ordinals."""

    def __init__(self, codepage_name):
        """Read a codepage file and convert to codepage dict."""
        self._mapping = {}
        data = pkgutil.get_data(__name__, 'codepages/{}.ucp'.format(codepage_name))
        if data is None:
            raise LookupError(codepage_name)
        for line in data.decode('utf-8-sig').splitlines():
            # ignore empty lines and comment lines (first char is #)
            if (not line) or (line[0] == '#'):
                continue
            # strip off comments; split unicodepoint and hex string
            splitline = line.split('#')[0].split(':')
            # ignore malformed lines
            if len(splitline) < 2:
                continue
            try:
                # extract codepage point
                cp_point = int(splitline[0].strip(), 16)
                # allow sequence of code points separated by commas
                #grapheme_cluster = ','.join(
                #    str(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(',')
                #)
                self._mapping[cp_point] = int(splitline[1], 16)
            except (ValueError, TypeError):
                logging.warning('Could not parse line in codepage file: %s', repr(line))
        self._inv_mapping = {_v: _k for _k, _v in self._mapping.items()}

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode label."""
        try:
            return 'u+{:04x}'.format(self._mapping[int(ordinal)])
        except KeyError as e:
            raise ValueError(str(e)) from e

    def unicode_to_ord(self, key, errors='strict'):
        """Convert ordinal to unicode label."""
        uniord = int(str(key)[2:], 16)
        try:
            return self._inv_mapping[uniord]
        except KeyError as e:
            if errors == 'strict':
                raise ValueError(str(e)) from e
            if errors == 'ignore':
                return self._inv_mapping[ord(' ')]
            # TODO: should we use replacement char? default-char?
            return self._inv_mapping[ord('?')]


class Unicode:
    """Convert between unicode and ordinals."""

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode label."""
        return 'u+{:04x}'.format(int(ordinal))

    def unicode_to_ord(self, key, errors='strict'):
        """Convert ordinal to unicode label."""
        return int(str(key)[2:], 16)


def _get_encoding(enc):
    """Find an encoding by name."""
    enc = enc.lower().replace('-', '_')
    if enc in ('unicode', 'ucs', 'iso10646', 'iso_10646', 'iso10646_1'):
        return Unicode()
    try:
        return Codepage(enc.lower())
    except LookupError:
        pass
    try:
        return Codec(enc.lower())
    except LookupError:
        pass
    logging.warning('Unknown encoding `%s`, assuming ascii.', enc)
    return Codec('ascii')


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs, labels=None, comments=(), properties=None):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        if not labels:
            labels = {_i: _i for _i in range(len(glyphs))}
        self._labels = {Label(_k): _v for _k, _v in labels.items()}
        if isinstance(comments, dict):
            # per-property comments
            self._comments = comments
        else:
            # global comments only
            self._comments = {None: comments}
        self._properties = {}
        if properties:
            properties = {_k.replace('_', '-'): _v for _k, _v in properties.items()}
            for key, converter in PROPERTIES.items():
                try:
                    value = converter(properties.pop(key))
                except KeyError:
                    continue
                except ValueError as e:
                    logging.error('Could not set property %s: %s', key, e)
                # don't set property values that equal the default
                default_value = getattr(self, key)
                if value != default_value:
                    self._properties[key] = value
            # append nonstandard properties
            self._properties.update(properties)
        self._encoding = _get_encoding(self._properties['encoding'])
        # add unicode labels for ordinals
        uni_labels = {}
        for _k, _v in self._labels.items():
            if not _k.is_ordinal:
                continue
            try:
                label = Label(self._encoding.ord_to_unicode(_k))
            except ValueError:
                pass
            else:
                uni_labels[label] = _v
        # add unicode glyph namr as comment
        self._glyphs = list(self._glyphs)
        for label, index in self._labels.items():
            if label.is_unicode and label.unicode_name and not self._glyphs[index].comments:
                self._glyphs[index] = self._glyphs[index].add_comments((label.unicode_name,))
        self._glyphs = tuple(self._glyphs)
        # override with explicit unicode labels, if given
        uni_labels.update(self._labels)
        self._labels = uni_labels


    ##########################################################################
    # glyph access

    def __iter__(self):
        """Iterate over labels, glyph pairs."""
        for index, glyph in enumerate(self._glyphs):
            labels = tuple(_label for _label, _index in self._labels.items() if _index == index)
            yield labels, glyph

    def get_glyph(self, key, default=True):
        """Get glyph by key, default if not present."""
        try:
            index = self._labels[Label(key)]
        except KeyError:
            if not default:
                raise
            return self.get_default_glyph()
        return self._glyphs[index]

    def get_default_glyph(self):
        """Get default glyph; empty if not defined"""
        try:
            default_key = self._labels[self.default_char]
            return self._glyphs[default_key]
        except KeyError:
            return Glyph.empty(*self.bounding_box)

    def get_char(self, key, errors='strict'):
        """Get glyph by unicode character."""
        try:
            return self.get_glyph('u+{:04x}'.format(ord(key)))
        except KeyError:
            pass
        return self.get_glyph(self._encoding.unicode_to_ord(key, errors=errors))

    def iter_unicode(self):
        """Iterate over glyphs with unicode labels."""
        for index, glyph in enumerate(self._glyphs):
            labels = tuple(
                _label for _label, _index in self._labels.items()
                if _index == index
            )
            for label in labels:
                if label.is_unicode:
                    yield label, glyph
                elif label.is_ordinal:
                    try:
                        yield self._encoding.ord_to_unicode(label), glyph
                    except ValueError:
                        pass

    ##########################################################################
    # labels

    @property
    def max_ordinal(self):
        """Get maximum ordinal in font."""
        ordinals = self.ordinals
        if ordinals:
            return max(ordinals)
        return -1

    @property
    def ordinal_range(self):
        """Get range of ordinals."""
        return range(0, self.max_ordinal + 1)

    @property
    def ordinals(self):
        """Get tuple of defined ordinals."""
        return sorted(int(_k) for _k in self._labels if _k.is_ordinal)

    @property
    def all_ordinal(self):
        """All glyphs except the default have ordinals."""
        return set(self._labels) <= set(self.ordinals)

    @property
    def number_glyphs(self):
        """Get number of glyphs in font."""
        return len(self._glyphs)

    def get_ordinal_for_label(self, key):
        """Get ordinal for given label, if defined."""
        key = Label(key)
        try:
            # maybe it's an ordinal already
            return int(key)
        except TypeError:
            pass
        try:
            index = self._labels[key]
        except KeyError:
            if key.is_unicode:
                return self._encoding.unicode_to_ord(key)
            raise
        for label, lindex in self._labels.items():
            if index == lindex and label.is_ordinal:
                return label
        raise KeyError(key)


    ##########################################################################
    # comments

    def get_comments(self, key=None):
        """Get a comment for a key, or global comment if no key provided."""
        return self._comments.get(key, [])


    ##########################################################################
    # properties

    def set_properties(self, **kwargs):
        """Return a copy with amended properties."""
        return Font(
            self._glyphs, self._labels, self._comments, {**self._properties, **kwargs}
        )

    @property
    def nondefault_properties(self):
        """Non-default properties."""
        return {**self._properties}

    def __getattr__(self, attr):
        """Take property from property table."""
        attr = attr.replace('_', '-')
        try:
            return self._properties[attr]
        except KeyError:
            pass
        try:
            # if in yaff property list, return default
            return self._yaff_properties[attr]
        except KeyError:
            pass
        try:
            # if in yaff property list, return default
            return PROPERTIES[attr]()
        except KeyError as e:
            raise AttributeError from e

    def yaffproperty(fn):
        """Take property from property table, if defined; calculate otherwise."""
        @wraps(fn)
        def _cached_fn(self, *args, **kwargs):
            try:
                return self._properties[fn.__name__.replace('_', '-')]
            except KeyError:
                pass
            return fn(self, *args, **kwargs)
        return property(_cached_fn)

    # default properties

    _yaff_properties = {
        'revision': '0', # font version
        'weight': 'regular', # normal, bold, light, etc.
        'slant': 'roman', # roman, italic, oblique, etc
        'setwidth': 'normal', # normal, condensed, expanded, etc.
        'direction': 'left-to-right', # left-to-right, right-to-left
        'encoding': 'ascii',
        'default-char': 'u+003f', # use question mark to replace missing glyph
        'word-boundary': 'u+0020', # word-break character (usually space)
    }

    @yaffproperty
    def name(self):
        """Name of font."""
        # maybe include slant, weight?
        return '{} {}px'.format(self.family, self.size.y).strip()

    @yaffproperty
    def family(self):
        """Name of font family."""
        if 'name' in self._properties:
            return self._properties['name'].split(' ')[0]
        # use source name if no family name or name defined
        if 'source-name' in self._properties:
            return self.source_name
        return ''

    @yaffproperty
    def point_size(self):
        """Nominal point height."""
        if 'dpi' in self._properties and 'pixel-size' in self._properties:
            # assume 72 points per inch (officially 72.27 pica points per inch)
            return int(self.pixel_size * self.dpi.y / 72.)
        # if dpi not given assume 72 dpi?
        return self.pixel_size

    @yaffproperty
    def pixel_size(self):
        """Get nominal pixel size (defaults to ascent)."""
        if not self._glyphs:
            return 0
        return self.ascent

    @yaffproperty
    def ascent(self):
        """Get ascent (defaults to max ink height above baseline)."""
        if not self._glyphs:
            return 0
        # this assumes matrix does not extend beyond font bounding box (no empty lines)
        # but using ink_height would assume there's a glyph that both fully ascends and fully descends
        # FIXME: need something like Glyph.bounding_box
        return max(_glyph.height for _glyph in self._glyphs) + self.offset

    @yaffproperty
    def descent(self):
        """Get descent (defaults to bottom/vertical offset)."""
        if not self._glyphs:
            return 0
        # this assumes matrix does not extend beyond font bounding box (no empty lines)
        return self.offset

    @yaffproperty
    def dpi(self):
        """Target screen resolution in dots per inch."""
        if 'point-size' in self._properties and 'pixel-size' in self._properties:
            dpi = (72 * self.pixel_size) // self.point_size
            return Coord(dpi, dpi)
        # default: 72 dpi; 1 point == 1 pixel
        return Coord(72, 72)

    @property
    def bounding_box(self):
        """Get maximum ink width and height, in pixels."""
        if not self._glyphs:
            return (0, 0)
        # the max raster width/height and max *ink* width/height *should* be the same
        return Coord(
            max(_glyph.width for _glyph in self._glyphs),
            max(_glyph.height for _glyph in self._glyphs)
        )

    @property
    def average_width(self):
        """Get average ink width, rounded to tenths of pixels."""
        if not self._glyphs:
            return 0
        return round(
            sum(_glyph.ink_width for _glyph in self._glyphs) / len(self._glyphs),
            1
        )

    @yaffproperty
    def spacing(self):
        """Monospace or proportional spacing."""
        if not self._glyphs:
            fixed = True
        else:
            sizes = set((_glyph.width, _glyph.height) for _glyph in self._glyphs)
            fixed = len(sizes) <= 1
        if fixed:
            return 'monospace'
        return 'proportional'

    @yaffproperty
    def x_width(self):
        """Width of uppercase X."""
        try:
            return self.get_char('X').ink_width
        except KeyError:
            return 0

    @yaffproperty
    def x_height(self):
        """Ink height of lowercase x."""
        try:
            return self.get_char('x').ink_height
        except KeyError:
            return 0

    @yaffproperty
    def cap_height(self):
        """Ink height of uppercase X."""
        try:
            return self.get_char('X').ink_height
        except KeyError:
            return 0

    ##########################################################################
    # font operations

    @scriptable
    def renumber(self, add:int=0):
        """Return a font with renumbered keys."""
        labels = {
            (Label(int(_k) + add) if _k.is_ordinal else _k): _v
            for _k, _v in self._labels.items()
        }
        return Font(self._glyphs, labels, self._comments, self._properties)

    @scriptable
    def subrange(self, from_:int=0, to_:int=None):
        """Return a continuous subrange of the font."""
        return self.subset(range(from_, to_))

    @scriptable
    def subset(self, keys:set=None):
        """Return a subset of the font."""
        if keys is None:
            keys = self._labels.keys()
        labels = {_k: _v for _k, _v in self._labels.items() if _k in keys}
        indexes = sorted(set(_v for _k, _v in self._labels.items()))
        glyphs = [self._glyphs[_i] for _i in indexes]
        return Font(glyphs, labels, self._comments, self._properties)

    ##########################################################################
    # inject Glyph operations into Font

    for _name, _func in Glyph.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a font with modified glyphs."""
                glyphs = [
                    operation(_glyph, *args, **kwargs)
                    for _glyph in self._glyphs
                ]
                return Font(glyphs, self._labels, self._comments, self._properties)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
