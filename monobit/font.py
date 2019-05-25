"""
monobit.font - representation of font

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from functools import wraps
from typing import NamedTuple

from .base import scriptable
from .glyph import Glyph


class Coord(NamedTuple):
    """Coordinate tuple."""
    x: int
    y: int


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs, labels=None, comments=(), properties=None):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        if not labels:
            labels = {_i: _i for _i in range(len(glyphs))}
        self._labels = labels
        if isinstance(comments, dict):
            # per-property comments
            self._comments = comments
        else:
            # global comments only
            self._comments = {None: comments}
        self._properties = properties or {}

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
            index = self._labels[key]
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
            #FIXME: convert all labels / props to lowercase?
            return self.get_glyph('u+{:04x}'.format(ord(key)))
        except KeyError:
            pass
        try:
            return self.get_glyph(key.encode(self.encoding))
        except UnicodeEncodeError:
            # errors='strict' (raise), 'replace' (with default), 'ignore' (replace with space)
            if errors == 'strict':
                raise
            elif errors == 'ignore':
                return self.get_glyph(' '.encode(self.encoding))
            return self.get_default_glyph()


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
        default_key = self._labels.get(None, None)
        return sorted(_k for _k in self._labels if isinstance(_k, int) and _k != default_key)

    @property
    def all_ordinal(self):
        """All glyphs except the default have ordinals."""
        default_key = self._labels.get(None, None)
        return set(self._labels) - set(self.ordinals) <= set([default_key])

    @property
    def number_glyphs(self):
        """Get number of glyphs in font."""
        return len(self._glyphs)

    def get_ordinal_for_label(self, key):
        """Get ordinal for given label, if defined."""
        try:
            # maybe it's an ordinal already
            return int(key, 0)
        except ValueError:
            pass
        try:
            index = self._labels[key]
        except KeyError:
            if key.startswith('u+'):
                # get ordinal for unicode by encoding
                unicode = int(key[2:], 16)
                byte = chr(unicode).encode(self.encoding, errors='ignore')
                if byte:
                    return byte[0]
            raise
        for label, lindex in self._labels.items():
            if index == lindex and isinstance(label, int):
                return label
        raise KeyError(key)


    ##########################################################################
    # properties

    def __getattr__(self, attr):
        """Take property from property table."""
        try:
            return self._properties[attr.replace('_', '-')]
        except KeyError as e:
            pass
        try:
            # if in yaff property list, return default
            return self._yaff_properties[attr.replace('_', '-')]
        except KeyError as e:
            raise AttributeError from e

    def yaffproperty(fn):
        """Take properrty from property table, if defined; calculate otherwise."""
        @wraps(fn)
        def _cached_fn(self, *args, **kwargs):
            try:
                return self._properties[fn.__name__.replace('_', '-')]
            except KeyError:
                pass
            return fn(self, *args, **kwargs)
        return property(_cached_fn)

    # yaff recognised properties and their defaults

    _yaff_properties = {
        ##'name': '', # full human name
        'foundry': '', # author or issuer
        'copyright': '', # copyright string
        'notice': '', # e.g. license string
        'revision': 0, # font version

        # descriptive:
        ##'point-size', # nominal point size
        ##'pixel-size', # nominal pixel size
        ##'dpi', # target resolution in dots per inch
        ##'family', # typeface/font family
        'weight': 'normal', # normal, bold, light, etc.
        'slant': 'roman', # roman, italic, oblique, etc
        'setwidth': 'normal', # normal, condensed, expanded, etc.
        'style': '', # serif, sans, etc.
        'decoration': '', # underline, strikethrough, etc.

        # these can be determined from the bitmaps
        ##'spacing', # proportional, monospace, cell
        ##'x-width', # ink width of lowercase x (in proportional font)
        ##'average-width', # average ink width, rounded to tenths
        ##'bounding-box', # maximum ink width/height

        # positioning relative to origin:
        'direction': 'left-to-right', # left-to-right, right-to-left
        'bottom': 0, # bottom line of matrix relative to baseline ## `drop`/`lift`? `offset-y`? `offset-transverse`?
        'offset-before': 0, # horizontal offset from origin to matrix start
        'offset-after': 0, # horizontal offset from matrix end to next origin

        # other metrics (may affect interline spacing):
        #'ascent', # recommended typographic ascent relative to baseline (not necessarily equal to top)
        #'descent', # recommended typographic descent relative to baseline (not necessarily equal to bottom)
        'leading': 0, # vertical leading, defined as (pixels between baselines) - (pixel height)
        ##'x-height', # height of lowercase x relative to baseline
        ##'cap-height', # height of capital relative to baseline

        # character set:
        'encoding': 'ascii',
        'default-char': 'u+003f', # use question mark to replace missing glyph
        'word-boundary': 'u+0020', # word-break character (usually space)

        # other
        'device': '', # target device name

        # conversion metadata:
        'converter': '',
        'source-name': '',
        'source-format': '',
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
        return max(_glyph.height for _glyph in self._glyphs) + self.bottom

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
            (_k + add if isinstance(_k, int) else _k): _v
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
                return Font(glyphs, self._comments, self._properties)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
