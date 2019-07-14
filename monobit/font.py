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


class KerningTable:
    """(Label, Label) -> int."""

    def __init__(self, table=None):
        """Set up kerning table."""
        if not table:
            table = {}
        if isinstance(table, str):
            table = {
                tuple(_row.split()[:2]): _row.split()[2]
                for _row in table.splitlines()
            }
        self._table = {
            (Label(_k[0]), Label(_k[1])): int(_v)
            for _k, _v in table.items()
        }

    def __str__(self):
        """Convert kerning table to multiline string."""
        return '\n'.join(
            f'{_k[0]} {_k[1]} {_v}'
            for _k, _v in self._table.items()
        )

    def items(self):
        """Iterate over items."""
        return self._table.items()



# recognised yaff properties and converters from str
# this also defines the default order in yaff files
PROPERTIES = {
    # font metadata
    # can't be calculated
    'name': str, # full human name
    'foundry': str, # author or issuer
    'copyright': str, # copyright string
    'notice': str, # e.g. license string
    'revision': str, # font version

    # font description
    # can't be calculated
    'family': str, # typeface/font family
    'style': str, # serif, sans, etc.
    'point-size': number, # nominal point size
    'weight': str, # normal, bold, light, etc.
    'slant': str, # roman, italic, oblique, etc
    'setwidth': str, # normal, condensed, expanded, etc.
    'decoration': str, # underline, strikethrough, etc.

    # target info
    # can't be calculated
    'device': str, # target device name
    'dpi': Coord.create, # target resolution in dots per inch

    # summarising quantities
    # determined from the bitmaps only
    'spacing': str, # proportional, monospace, character-cell, multi-cell
    'bounding-box': Coord.create, # maximum ink width/height
    'average-advance': number, # average advance width, rounded to tenths
    'cap-advance': int, # advance width of LATIN CAPITAL LETTER X

    # descriptive typographic quantities
    # can be calculated or given
    'x-height': int, # height of lowercase x relative to baseline
    'cap-height': int, # height of capital relative to baseline
    # can't be calculated, don't currently affect rendering
    # might affect e.g. composition of characters
    'ascent': int, # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent': int, # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'pixel-size': int, # nominal pixel size, always equals ascent + descent

    # metrics
    # can't be calculated, affect rendering
    # positioning relative to origin
    'direction': str, # left-to-right, right-to-left
    'offset': Coord.create, # (horiz, vert) offset from origin to matrix start
    'tracking': int, # horizontal offset from matrix end to next origin
    'leading': int, # interline spacing, defined as (pixels between baselines) - (bounding box height)

    # character set
    # can't be calculated, affect rendering
    'encoding': str,
    'default-char': Label, # use question mark to replace missing glyph
    'word-boundary': Label, # word-break character (usually space)

    # conversion metadata
    # can't be calculated, informational
    'converter': str,
    'source-name': str,
    'source-format': str,

    # kerning table (at the end because it's long)
    # pairwise kerning (defined as adjustment to tracking)
    'kerning': KerningTable,
}

# calculated properties
# properties that must have the calculated value
_NON_OVERRIDABLE = ('spacing', 'bounding-box', 'pixel-size', 'average-advance', 'cap-advance',)
# properties where the calculated vale may be overridden
_OVERRIDABLE = ('x-height', 'cap-height',)


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

    def unicode_to_ord(self, key):
        """Convert ordinal to unicode label."""
        unicode = Label(key).unicode
        uniord = ord(unicode)
        byte = unicode.encode(self._encoding, errors='strict')
        return byte[0]


class Codepage:
    """Convert between unicode and ordinals."""

    def __init__(self, codepage_name):
        """Read a codepage file and convert to codepage dict."""
        codepage_name = codepage_name.replace('_', '-')
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
                self._mapping[cp_point] = ''.join(
                    chr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(',')
                )
            except (ValueError, TypeError):
                logging.warning('Could not parse line in codepage file: %s', repr(line))
        self._inv_mapping = {_v: _k for _k, _v in self._mapping.items()}

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode label."""
        try:
            return str(Label.from_unicode(self._mapping[int(ordinal)]))
        except KeyError as e:
            raise ValueError(str(e)) from e

    def unicode_to_ord(self, key):
        """Convert ordinal to unicode label."""
        unicode = Label(key).unicode
        try:
            return self._inv_mapping[unicode]
        except KeyError as e:
            raise ValueError(str(e)) from e


class Unicode:
    """Convert between unicode and ordinals."""

    @staticmethod
    def ord_to_unicode(ordinal):
        """Convert ordinal to unicode label."""
        return str(Label.from_unicode(chr(int(ordinal))))

    @staticmethod
    def unicode_to_ord(key):
        """Convert ordinal to unicode label."""
        uc = Label(key).unicode
        if len(uc) > 1:
            # grapheme clusters
            # when encoding == Unicode we shouldn't really need unicode_to_ord
            # however if we do, grapheme clusters are not supported
            raise ValueError(str(key))
        return ord(uc)


class NoEncoding:

    @staticmethod
    def ord_to_unicode(ordinal):
        raise ValueError(ordinal)

    @staticmethod
    def unicode_to_ord(key):
        raise ValueError(str(key))


_ENCODING_ALIASES = {
    'ucs': 'unicode',
    'iso10646': 'unicode',
    'iso10646-1': 'unicode',
    'iso8859-1': 'latin-1',
    'iso646-us': 'ascii',
    'ascii-0': 'ascii',
}

def normalise_encoding(encoding):
    """Replace encoding name with normalised variant."""
    encoding = encoding.lower().replace('_', '-')
    return _ENCODING_ALIASES.get(encoding, encoding)


def _get_encoding(enc):
    """Find an encoding by name."""
    enc = enc.lower().replace('-', '_')
    if normalise_encoding(enc) == 'unicode':
        return Unicode
    try:
        return Codepage(enc)
    except LookupError:
        pass
    try:
        return Codec(enc)
    except LookupError:
        pass
    logging.warning('Unknown encoding `%s`.', enc)
    return NoEncoding


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
        # set encoding first so we can set labels
        self._add_unicode_data(properties.get('encoding', None))
        # identify multi-codepoint clusters
        # we've already added unicode labels for codepage ordinals, so those should be included.
        self._grapheme_clusters = set(
            _label.unicode for _label in self._labels
            if _label.is_unicode and len(_label.unicode) > 1
        )
        # update properties
        if properties:
            properties = {_k.replace('_', '-'): _v for _k, _v in properties.items()}
            for key, converter in reversed(list(PROPERTIES.items())):
                # we've already set the encoding
                if key == 'encoding':
                    continue
                try:
                    value = converter(properties.pop(key))
                except KeyError:
                    continue
                except ValueError as e:
                    logging.error('Could not set property %s: %s', key, e)
                # don't set property values that equal the default
                # we need to ensure we use underscore variants, or default functions won't get called
                default_value = getattr(self, key.replace('-', '_'))
                if value != default_value:
                    if key in _NON_OVERRIDABLE:
                        logging.warning(
                            "Property `%s` value can't be set to %s. Keeping calculated value %s.",
                            key, str(value), str(default_value)
                        )
                    else:
                        self._properties[key] = value
                        if key in _OVERRIDABLE:
                            logging.info(
                                'Property `%s` value set to %s, while calculated value is %s.',
                                key, str(value), str(default_value)
                            )
            # append nonstandard properties
            self._properties.update(properties)

    def __repr__(self):
        """Representation."""
        return f"<Font '{self.name}'>"

    def _add_unicode_data(self, encoding=None):
        """Add unicode labels and comments."""
        if encoding:
            self._properties['encoding'] = normalise_encoding(encoding)
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
        # override with explicit unicode labels, if given
        uni_labels.update(self._labels)
        self._labels = uni_labels
        # add unicode glyph name as comment
        self._glyphs = list(self._glyphs)
        for label, index in self._labels.items():
            if label.is_unicode and label.unicode_name and not self._glyphs[index].comments:
                if unicodedata.category(label.unicode).startswith('C'):
                    description = '{}'.format(label.unicode_name)
                else:
                    description = '[{}] {}'.format(label.unicode, label.unicode_name)
                self._glyphs[index] = self._glyphs[index].add_comments((description,))
        self._glyphs = tuple(self._glyphs)


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
        return Glyph.empty(max(0, -self.offset.x - self.tracking), self.bounding_box.y)

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
            # we don't check ordinals and codepage
            # as we have already added unicode labels for ordinals in __init__
            return self._get_fallback_glyph(key, missing)
        return self.get_glyph(ordinal, missing=missing)

    def _iter_string(self, string, missing='raise'):
        """Iterate over string, yielding unicode characters."""
        remaining = string
        while remaining:
            # try grapheme clusters first
            for cluster in self._grapheme_clusters:
                if remaining.startswith(cluster):
                    unicode = cluster
                    remaining = remaining[len(cluster):]
                    break
            else:
                unicode, remaining = remaining[0], remaining[1:]
            yield unicode

    def render(self, text, fore=1, back=0, *, margin=(0, 0), scale=(1, 1), missing='default'):
        """Render text string to bitmap."""
        margin_x, margin_y = margin
        chars = [
            list(self._iter_string(_line))
            for _line in text.splitlines()
        ]
        glyphs = [
            [self.get_char(_c, missing=missing) for _c in _line]
            for _line in chars
        ]
        if self.kerning:
            kerning = {
                (self.get_unicode_for_label(_key[0]), self.get_unicode_for_label(_key[1])): _value
                for _key, _value in self.kerning.items()
            }
            kernings = [
                [
                    kerning.get((_char, _next), 0)
                    for _char, _next in zip(_line[:-1], _line[1:])
                ] + [0]
                for _line in chars
            ]
        else:
            kernings = [[0] * len(_line) for _line in chars]
        # determine dimensions
        if not glyphs:
            width = 2 * margin_x
        else:
            width = 2 * margin_x + max(
                (
                    sum(_glyph.width for _glyph in _row)
                    + (self.offset.x + self.tracking) * len(_row)
                )
                for _row in glyphs
            )
        line_height = self.bounding_box.y + self.leading
        height = 2 * margin_y + line_height * len(glyphs)
        line_output = [
            [0 for _ in range(width)]
            for _ in range(height)
        ]
        # get to initial origin
        grid_top = margin_y
        for row, kernrow in zip(glyphs, kernings):
            x, y = 0, 0
            for glyph, kerning in zip(row, kernrow):
                matrix = glyph.as_matrix(1, 0)
                # apply pre-offset so that x,y is logical coordinate of grid origin
                x, y = x + self.offset.x, y + self.offset.y
                # grid coordinates of grid origin
                grid_x, grid_y = margin_x + x, grid_top + self.ascent - y
                # add ink, taking into account there may be ink already in case of negative bearings
                for work_y in range(glyph.height):
                    if 0 <= grid_y - work_y < height:
                        row = line_output[grid_y - work_y]
                        for work_x, ink in enumerate(matrix[glyph.height - work_y - 1]):
                            if 0 <= grid_x + work_x < width:
                                row[grid_x + work_x] |= ink
                # advance
                x += glyph.width
                # apply post-offset
                x, y = x + self.tracking + kerning, y - self.offset.y
            grid_top += line_height
        output = []
        output.extend(line_output)
        scale_x, scale_y = scale
        output = tuple(
            tuple((fore if _item else back) for _item in _row for _ in range(scale_x))
            for _row in output for _ in range(scale_y)
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
        # maybe it's an ordinal already
        if key.is_ordinal:
            return int(key)
        index = self._labels[key]
        for label, lindex in self._labels.items():
            if index == lindex and label.is_ordinal:
                return int(label)
        raise KeyError(f'No ordinal found for label `{key}`')

    def get_unicode_for_label(self, key):
        """Get unicode for given label, if defined."""
        key = Label(key)
        if key.is_unicode:
            return key.unicode
        if key.is_ordinal and self._encoding == Unicode:
            return chr(int(key))
        index = self._labels[key]
        for label, lindex in self._labels.items():
            if index == lindex and label.is_unicode:
                return label.unicode
        raise KeyError(f'No unicode codepoint found for label `{key}`')


    ##########################################################################
    # comments

    def get_comments(self, key=None):
        """Get a comment for a key, or global comment if no key provided."""
        return self._comments.get(key, [])

    @scriptable
    def add_comments(self, new_comment:str='', key:str=None):
        """Get a comment for a key, or global comment if no key provided."""
        comments = {**self._comments}
        if key not in comments:
            comments[key] = []
        comments[key] = list(comments[key]) + new_comment.splitlines()
        return Font(self._glyphs, self._labels, comments, self._properties)


    ##########################################################################
    # properties

    @scriptable
    def set_encoding(self, encoding:str=''):
        """
        Return a copy with ordinals relabelled through a different codepage.
        Text and unicode labels and glyph comments are dropped.
        """
        labels = {_k: _v for _k,_v in self._labels.items() if _k.is_ordinal}
        glyphs = [_glyph.drop_comments() for _glyph in self._glyphs]
        properties = {**self._properties}
        properties['encoding'] = encoding
        return Font(glyphs, labels, self._comments, properties)

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
        'encoding': '',
        'word-boundary': 'u+0020', # word-break character (usually space)
    }

    @yaffproperty
    def name(self):
        """Name of font."""
        weight = '' if self.weight == self._yaff_properties['weight'] else self.weight.title()
        slant = '' if self.slant == self._yaff_properties['slant'] else self.slant.title()
        #encoding = '' if self.encoding == self._yaff_properties['encoding'] else f'({self.encoding})'
        return ' '.join(
            str(_x) for _x in (self.family, weight, slant, self.point_size) if _x
        )

    @yaffproperty
    def family(self):
        """Name of font family."""
        # use source name if no family name defined
        if 'source-name' in self._properties:
            return self.source_name.split('.')[0]
        return ''

    @yaffproperty
    def point_size(self):
        """Nominal point height."""
        # assume 72 points per inch (officially 72.27 pica points per inch)
        # if dpi not given assumes 72 dpi, so point-size == pixel-size
        return int(self.pixel_size * self.dpi.y / 72.)

    @yaffproperty
    def pixel_size(self):
        """Get nominal pixel size (ascent + descent)."""
        if not self._glyphs:
            return 0
        return self.ascent + self.descent

    @yaffproperty
    def ascent(self):
        """Get ascent (defaults to max ink height above baseline)."""
        if not self._glyphs:
            return 0
        return self.offset.y + max(
            # ink_offsets[3] is offset from top
            _glyph.height - _glyph.ink_offsets[3]
            for _glyph in self._glyphs
        )

    @yaffproperty
    def descent(self):
        """Get descent (defaults to bottom/vertical offset)."""
        if not self._glyphs:
            return 0
        # ink_offsets[1] is offset from bottom
        # usually, descent is positive and offset is negative
        # negative descent would mean font descenders are all above baseline
        return -self.offset.y - min(_glyph.ink_offsets[1] for _glyph in self._glyphs)

    @yaffproperty
    def dpi(self):
        """Target screen resolution in dots per inch."""
        # if point-size has been overridden and dpi not set, determine from pixel-size & point-size
        if 'point-size' in self._properties:
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

    @yaffproperty
    def average_advance(self):
        """Get average glyph advance width, rounded to tenths of pixels."""
        if not self._glyphs:
            return self.offset.x + self.tracking
        return (
            self.offset.x
            + sum(_glyph.width for _glyph in self._glyphs) / len(self._glyphs)
            + self.tracking
        )

    @yaffproperty
    def spacing(self):
        """Monospace or proportional spacing."""
        if not self._glyphs:
            return 'character-cell'
        widths = set(_glyph.width for _glyph in self._glyphs)
        heights = set(_glyph.height for _glyph in self._glyphs)
        min_width = min(widths)
        # mono- or multi-cell fonts: equal heights, no ink outside cell, widths are fixed multiples
        charcell = (
            len(heights) == 1
            and self.offset.x >= 0 and self.tracking >= 0 and self.leading >= 0
            and min_width > 3 and not any(_width % min_width for _width in widths)
        )
        if charcell:
            if len(widths) == 1:
                return 'character-cell'
            return 'multi-cell'
        if len(widths) == 1:
            return 'monospace'
        return 'proportional'

    @yaffproperty
    def cap_advance(self):
        """Advance width of uppercase X."""
        try:
            return self.get_char('X').width + self.offset.x + self.tracking
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
