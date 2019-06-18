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

    def __init__(self, value=''):
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
        value = value.strip()
        # see if it counts as unicode label
        if value.lower().startswith('u+'):
            try:
                [int(_elem.strip()[2:], 16) for _elem in value.split(',')]
            except ValueError as e:
                raise ValueError("'{}' is not a valid unicode label.".format(value)) from e
        # 'namespace' labels with a dot are not converted to lowercase
        if '.' in value:
            self._value = value
        else:
            self._value = value.lower()

    @classmethod
    def from_unicode(cls, unicode):
        """Convert ordinal to unicode label."""
        return ','.join(
            'u+{:04x}'.format(ord(_uc))
            for _uc in unicode
        )

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
            return ''.join(chr(int(_cp.strip()[2:], 16)) for _cp in self._value.split(',') if _cp)
        return ''

    @property
    def unicode_name(self):
        if self.is_unicode:
            try:
                return ', '.join(unicodedata.name(_cp) for _cp in self.unicode)
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
    'dpi': Coord.create, # target resolution in dots per inch
    'family': str, # typeface/font family
    'weight': str, # normal, bold, light, etc.
    'slant': str, # roman, italic, oblique, etc
    'setwidth': str, # normal, condensed, expanded, etc.
    'style': str, # serif, sans, etc.
    'decoration': str, # underline, strikethrough, etc.
    'x-height': int, # height of lowercase x relative to baseline
    'cap-height': int, # height of capital relative to baseline

    # these can be determined from the bitmaps
    'spacing': str, # proportional, monospace, cell
    'x-width': int, # ink width of lowercase x (in proportional font)
    'average-advance': number, # average advance width, rounded to tenths
    'bounding-box': Coord.create, # maximum ink width/height

    # positioning relative to origin:
    'direction': str, # left-to-right, right-to-left
    #TODO: change to offset (x y) and bearing (=bearing-after) ?
    'offset': int, # transverse offset: bottom line of matrix relative to baseline
    'bearing-before': int, # horizontal offset from origin to matrix start
    'bearing-after': int, # horizontal offset from matrix end to next origin

    # vertical metrics - affect interline spacing:
    'pixel-size': int, # nominal pixel size
    'ascent': int, # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent': int, # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'leading': int, # vertical leading, defined as (pixels between baselines) - (pixel height)

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
        return str(Label.from_unicode(unicode))

    def unicode_to_ord(self, key, errors='strict'):
        """Convert ordinal to unicode label."""
        unicode = Label(key).unicode
        uniord = ord(unicode)
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
        try:
            data = pkgutil.get_data(__name__, 'codepages/{}.ucp'.format(codepage_name))
        except EnvironmentError:
            # "If the package cannot be located or loaded, then None is returned." say the docs
            # but it seems to raise FileNotFoundError if the *resource* isn't there
            data = None
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
            return str(Label.from_unicode(chr(self._mapping[int(ordinal)])))
        except KeyError as e:
            raise ValueError(str(e)) from e

    def unicode_to_ord(self, key, errors='strict'):
        """Convert ordinal to unicode label."""
        uniord = ord(Label(key).unicode)
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

    @staticmethod
    def ord_to_unicode(ordinal):
        """Convert ordinal to unicode label."""
        return str(Label.from_unicode(chr(int(ordinal))))

    @staticmethod
    def unicode_to_ord(key, errors='strict'):
        """Convert ordinal to unicode label."""
        uc = Label(key).unicode
        # FIXME: deal with multichar grapheme clusters
        return ord(uc)


_UNICODE_ALIASES = ('unicode', 'ucs', 'iso10646', 'iso_10646', 'iso10646_1')

def encoding_is_unicode(encoding):
    """Check if an encoding name implies unicode."""
    return encoding.replace('-', '_') in _UNICODE_ALIASES


def _get_encoding(enc):
    """Find an encoding by name."""
    enc = enc.lower().replace('-', '_')
    if encoding_is_unicode(enc):
        return Unicode
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
        self._encoding = _get_encoding(self.encoding)
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
        # remove ordinal labels if encoding is unicode
        if self._encoding == Unicode:
            self._labels = {
                _k: _v for _k, _v in self._labels.items()
                if not _k.is_ordinal
            }
        # add unicode glyph namr as comment
        self._glyphs = list(self._glyphs)
        for label, index in self._labels.items():
            if label.is_unicode and label.unicode_name and not self._glyphs[index].comments:
                if unicodedata.category(label.unicode).startswith('C'):
                    description = '{}'.format(label.unicode_name)
                else:
                    description = '[{}] {}'.format(label.unicode, label.unicode_name)
                self._glyphs[index] = self._glyphs[index].add_comments((description,))
        self._glyphs = tuple(self._glyphs)
        # override with explicit unicode labels, if given
        uni_labels.update(self._labels)
        self._labels = uni_labels

    def __repr__(self):
        """Representation."""
        return f"<Font '{self.name}'>"

    ##########################################################################
    # glyph access

    def get_glyph(self, key, *, missing='raise'):
        """Get glyph by key, default if not present."""
        try:
            index = self._labels[Label(key)]
        except KeyError:
            return self._get_fallback_glyph(key, missing)
        return self._glyphs[index]

    def _get_fallback_glyph(self, key='', missing='raise'):
        """Get the fallback glyph."""
        if missing == 'default':
            return self.get_default_glyph()
        if missing == 'empty':
            return self.get_empty_glyph()
        raise KeyError(f'No glyph found matching {key}.')

    def get_default_glyph(self):
        """Get default glyph; empty if not defined."""
        try:
            default_key = self._labels[self.default_char]
            return self._glyphs[default_key]
        except KeyError:
            return self.get_empty_glyph()

    def get_empty_glyph(self):
        """Get empty glyph with minimal advance (zero if bearing 0 or negative)."""
        return Glyph.empty(max(0, -self.bearing_before - self.bearing_after), self.bounding_box.y)

    def __iter__(self):
        """Iterate over labels, glyph pairs."""
        for index, glyph in enumerate(self._glyphs):
            labels = tuple(_label for _label, _index in self._labels.items() if _index == index)
            yield labels, glyph

    def iter_unicode(self):
        """Iterate over glyphs with unicode labels."""
        for index, glyph in enumerate(self._glyphs):
            yield from (
                (_label, glyph) for _label, _index in self._labels.items()
                if _index == index and _label.is_unicode
            )

    def iter_ordinal(self, encoding=None, start=0, stop=None, missing='empty'):
        """Iterate over glyphs by ordinal; contiguous range."""
        start = start or 0
        stop = stop or 1 + max(int(_k) for _k in self._labels if _k.is_ordinal)
        if encoding:
            encoding = _get_encoding(encoding)
        for ordinal in range(start, stop):
            if not encoding:
                # use only whatever ordinal was provided
                label = ordinal
                try:
                    unicode = self._encoding.ord_to_unicode(ordinal)
                except ValueError:
                    unicode = ''
            else:
                # transcode from unicode labels
                try:
                    label = encoding.ord_to_unicode(ordinal)
                    unicode = label
                except ValueError:
                    # not in target encoding
                    continue
            yield Label(unicode), self.get_glyph(label, missing=missing)


    ##########################################################################
    # text / character access

    def get_char(self, key, missing='raise'):
        """Get glyph by unicode character."""
        label = Label.from_unicode(key)
        try:
            return self.get_glyph(label)
        except KeyError:
            pass
        try:
            ordinal = self._encoding.unicode_to_ord(label)
        except ValueError:
            return self._get_fallback_glyph(key, missing)
        return self.get_glyph(ordinal, missing=missing)

    def render(self, text, fore=1, back=0, *, offset_x=0, offset_y=0, missing='default'):
        """Render text string to bitmap."""
        if not text:
            return []
        # TODO: deal with grapheme clusters
        glyphs = [
            [self.get_char(_c, missing=missing) for _c in _line]
            for _line in text.splitlines()
        ]
        # determine dimensions
        width = offset_x + max(
            (
                sum(_glyph.width for _glyph in _row)
                + (self.bearing_before + self.bearing_after) * len(_row)
            )
            for _row in glyphs
        )
        height = offset_y + (self.pixel_size + self.leading) * len(glyphs)
        line_output = [
            [0 for _ in range(width)]
            for _ in range(height)
        ]
        # get to initial origin
        grid_top = offset_y
        for row in glyphs:
            x, y = 0, 0
            for glyph in row:
                matrix = glyph.as_matrix(1, 0)
                # apply pre-offset so that x,y is logical coordinate of grid origin
                x, y = x + self.bearing_before, y + self.offset
                # grid coordinates of grid origin
                grid_x, grid_y = offset_x + x, grid_top + self.ascent - y
                # add ink, taking into account there may be ink already in case of negtive bearings
                #for work_y, row in enumerate(line_output[grid_y-glyph.height:grid_y]):
                for work_y in range(glyph.height):
                    if 0 <= grid_y - work_y < height:
                        row = line_output[grid_y - work_y]
                        for work_x, ink in enumerate(matrix[glyph.height - work_y - 1]):
                            if 0 <= grid_x + work_x < width:
                                row[grid_x + work_x] |= ink
                # advance
                x += glyph.width
                # apply post-offset
                x, y = x + self.bearing_after, y - self.offset
            grid_top += self.leading + self.pixel_size
        output = []
        output.extend(line_output)
        output = tuple(
            tuple((fore if _item else back) for _item in _row)
            for _row in output
        )
        return output

    ##########################################################################
    # labels

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
        # FIXME: need something like Glyph.bounding_box and .offset
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
            return Coord(0, 0)
        # the max raster width/height and max *ink* width/height *should* be the same
        return Coord(
            max(_glyph.width for _glyph in self._glyphs),
            max(_glyph.height for _glyph in self._glyphs)
        )

    @yaffproperty
    def default_char(self):
        """Default character."""
        repl = Label('u+fffd')
        if repl in self._labels:
            return str(repl)
        return ''

    @property
    def average_width(self):
        """Get average glyph width, rounded to tenths of pixels."""
        if not self._glyphs:
            return 0
        return round(
            # ink_width ?
            sum(_glyph.width for _glyph in self._glyphs) / len(self._glyphs),
            1
        ) + self.bearing_before + self.bearing_after

    @yaffproperty
    def average_advance(self):
        """Get average advance width, rounded to tenths of pixels."""
        return self.average_width + self.bearing_before + self.bearing_after

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
        # TODO - distinguish "cell" spacing; e.g. equal widths, equal heights, no negative bearings
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
