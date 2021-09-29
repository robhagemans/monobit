"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import pkgutil
import logging
from pathlib import Path
import unicodedata

from pkg_resources import resource_listdir

from .base.binary import int_to_bytes


_ENCODING_ALIASES = {
    'ucs': 'unicode',
    'iso646-us': 'ascii',
    'us-ascii': 'ascii',
    'iso10646': 'unicode',

    # X11 / BDF encoding names
    'iso10646-1': 'unicode',
    'iso8859-1': 'latin-1',
    'ascii-0': 'ascii',
    #'microsoft-symbol': '', # http://www.kostis.net/charsets/symbol.htm
    #'microsoft-win3.1': '', # is this the windows-3.1 version of 'windows-ansi'?
    'armscii-8': 'armscii8a',

    # MIME / IANA names
    'macintosh': 'mac-roman',

    # others
    'mac-ce': 'mac-centraleurope',
    'mac-latin2': 'mac-centraleurope',
    'mac-centeuro': 'mac-centraleurope',
    'mac-east-eur-roman': 'mac-centraleurope',
    'mac-geez': 'mac-ethiopic',
    'mac-ext-arabic': 'mac-sindhi',

    'nextstep': 'next',
    'next-multinational': 'next',
    'strk1048-2002': 'kz-1048',
    'gsm-03.38': 'gsm',
}

# replacement patterns
_ENCODING_STARTSWITH = {
    'microsoft-cp': 'windows-',
    'ibm-cp': 'cp',
    'apple-': 'mac-',
    # mac-roman also known as x-mac-roman etc.
    'x-': '',
    'iso-': 'iso',
}

# iso standards
# https://www.unicode.org/Public/MAPPINGS/ISO8859
_ISO_ENCODINGS = {
    'iso8859-1': 'iso-8859/8859-1.TXT',
    'iso8859-2': 'iso-8859/8859-2.TXT',
    'iso8859-3': 'iso-8859/8859-3.TXT',
    'iso8859-4': 'iso-8859/8859-4.TXT',
    'iso8859-5': 'iso-8859/8859-5.TXT',
    'iso8859-6': 'iso-8859/8859-6.TXT',
    'iso8859-7': 'iso-8859/8859-7.TXT',
    'iso8859-8': 'iso-8859/8859-8.TXT',
    'iso8859-9': 'iso-8859/8859-9.TXT',
    'iso8859-10': 'iso-8859/8859-10.TXT',
    'iso8859-11': 'iso-8859/8859-11.TXT',
    'iso8859-13': 'iso-8859/8859-13.TXT',
    'iso8859-14': 'iso-8859/8859-14.TXT',
    'iso8859-15': 'iso-8859/8859-15.TXT',
    'iso8859-16': 'iso-8859/8859-16.TXT',
}

# Adobe encodings
# https://www.unicode.org/Public/MAPPINGS/VENDORS/ADOBE/
_ADOBE_ENCODINGS = {
    'adobe-standard': 'adobe/stdenc.txt',
    'adobe-symbol': 'adobe/symbol.txt',
    'adobe-dingbats': 'adobe/zdingbat.txt',
}

_APPLE_ENCODINGS = {
    # Apple codepages matching a script code
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/

    # Armenian and Georgian taken from Evertype:
    # https://www.evertype.com/standards/mappings/

    #'mac-roman': 'apple/ROMAN.TXT',
    # this has the pre-euro version of the mac-roman set (aka microsoft's cp 10000)
    'mac-roman': 'microsoft/MAC/ROMAN.TXT',

    'mac-japanese': 'apple/JAPANESE.TXT',
    'mac-trad-chinese': 'apple/CHINTRAD.TXT',
    'mac-korean': 'apple/KOREAN.TXT',
    'mac-arabic': 'apple/ARABIC.TXT',
    'mac-hebrew': 'apple/HEBREW.TXT',
    'mac-greek': 'apple/GREEK.TXT',
    # note: A2, B6, FF changed after mac-os 9.0
    # see https://en.wikipedia.org/wiki/Mac_OS_Cyrillic_encoding
    'mac-cyrillic': 'apple/CYRILLIC.TXT',
    'mac-devanagari': 'apple/DEVANAGA.TXT',
    'mac-gurmukhi': 'apple/GURMUKHI.TXT',
    'mac-gujarati': 'apple/GUJARATI.TXT',
    #'mac-oriya':
    #'mac-bengali':
    #'mac-tamil':
    #'mac-telugu':
    #'mac-kannada':
    #'mac-malayalam':
    #'mac-sinhalese':
    #'mac-burmese':
    #'mac-khmer':
    'mac-thai': 'apple/THAI.TXT',
    #'mac-laotian':
    'mac-georgian': 'evertype/mac/GEORGIAN.TXT',
    'mac-armenian': 'evertype/mac/ARMENIAN.TXT',
    'mac-simp-chinese': 'apple/CHINSIMP.TXT',
    #'mac-tibetan':
    #'mac-mongolian':
    #'mac-ethiopian',

    # "non-cyrillic slavic", mac-centeuro
    # cf. 'microsoft/MAC/LATIN2.TXT'
    'mac-centraleurope': 'apple/CENTEURO.TXT',

    #'mac-vietnamese':
    #'mac-sindhi':

    # Apple codepages not matching a script code

    'mac-celtic': 'apple/CELTIC.TXT',
    'mac-croatian': 'apple/CROATIAN.TXT',
    'mac-dingbats': 'apple/DINGBATS.TXT',
    'mac-farsi': 'apple/FARSI.TXT',
    'mac-gaelic': 'apple/GAELIC.TXT',
    'mac-icelandic': 'apple/ICELAND.TXT',
    'mac-inuit': 'apple/INUIT.TXT',
    'mac-symbol': 'apple/SYMBOL.TXT',
    'mac-turkish': 'apple/TURKISH.TXT',
    'mac-ukrainian': 'apple/UKRAINE.TXT',

    # Evertype
}

_MICROSOFT_ENCODINGS = {
    # Windows codepages
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/WINDOWS
    'windows-874': 'microsoft/WINDOWS/CP874.TXT',
    'windows-932': 'microsoft/WINDOWS/CP932.TXT',
    'windows-936': 'microsoft/WINDOWS/CP936.TXT',
    'windows-949': 'microsoft/WINDOWS/CP949.TXT',
    'windows-950': 'microsoft/WINDOWS/CP950.TXT',
    'windows-1250': 'microsoft/WINDOWS/CP1250.TXT',
    'windows-1251': 'microsoft/WINDOWS/CP1251.TXT',
    'windows-1252': 'microsoft/WINDOWS/CP1252.TXT',
    'windows-1253': 'microsoft/WINDOWS/CP1253.TXT',
    'windows-1254': 'microsoft/WINDOWS/CP1254.TXT',
    'windows-1255': 'microsoft/WINDOWS/CP1255.TXT',
    'windows-1256': 'microsoft/WINDOWS/CP1256.TXT',
    'windows-1257': 'microsoft/WINDOWS/CP1257.TXT',
    'windows-1258': 'microsoft/WINDOWS/CP1258.TXT',

    # IBM/OEM/MS-DOS codepages
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/PC
    'cp437': 'microsoft/PC/CP437.TXT',
    'cp737': 'microsoft/PC/CP737.TXT',
    'cp775': 'microsoft/PC/CP775.TXT',
    'cp850': 'microsoft/PC/CP850.TXT',
    'cp852': 'microsoft/PC/CP852.TXT',
    'cp855': 'microsoft/PC/CP855.TXT',
    'cp857': 'microsoft/PC/CP857.TXT',
    'cp860': 'microsoft/PC/CP860.TXT',
    'cp861': 'microsoft/PC/CP861.TXT',
    'cp862': 'microsoft/PC/CP862.TXT',
    'cp863': 'microsoft/PC/CP863.TXT',
    'cp864': 'microsoft/PC/CP864.TXT',
    'cp865': 'microsoft/PC/CP865.TXT',
    'cp866': 'microsoft/PC/CP866.TXT',
    'cp869': 'microsoft/PC/CP869.TXT',
    'cp874': 'microsoft/PC/CP874.TXT',

    # EBCDIC
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/EBCDIC
    'cp037': 'microsoft/PC/CP037.TXT',
    'cp500': 'microsoft/PC/CP500.TXT',
    'cp875': 'microsoft/PC/CP875.TXT',
    'cp1026': 'microsoft/PC/CP1026.TXT',
}

_OTHER_ENCODINGS = {
    'atari-st': ('misc/ATARIST.TXT', 'format_a'),
    # IBM PC memory-mapped video graphics, overlaying the control character range
    # to be used in combination with other code pages e.g. cp437
    'ibm-graphics': ('misc/IBMGRAPH.TXT', 'adobe'),
    'ibm-graphics-cp864': ('misc/IBMGRAPH.TXT', 'ibmgraph_864'),
    'koi8-r': ('misc/KOI8-R.TXT', 'format_a'),
    'koi8-u': ('misc/KOI8-U.TXT', 'format_a'),
    'cp424': ('misc/CP424.TXT', 'format_a'),
    'cp856': ('misc/CP856.TXT', 'format_a'),
    'cp1006': ('misc/CP1006.TXT', 'format_a'),
    'iso-ir-68': ('misc/APL-ISO-IR-68.TXT', 'format_a'),
    'kps-9566': ('misc/KPS9566.TXT', 'format_a'),
    'kz-1048': ('misc/KZ1048.TXT', 'format_a'),
    # not loaded from misc/:
    # SGML.TXT
    # US-ASCII-QUOTES.TXT
    'next': ('misc/NEXTSTEP.TXT', 'format_a'),
    'gsm': ('misc/GSM0338.TXT', 'format_a'),
}

# Freedos


# codepage file format parameters
_FORMATS = {
    'ucp': dict(comment='#', separator=':', joiner=',', codepoint_column=0, unicode_column=1),
    'adobe': dict(comment='#', separator='\t', joiner=None, codepoint_column=1, unicode_column=0),
    'format_a': dict(comment='#', separator=None, joiner='+', codepoint_column=0, unicode_column=1),
    'ibmgraph_864': dict(
        comment='#', separator='\t', joiner=None, codepoint_column=2, unicode_column=0
    ),
}


###################################################################################################

def normalise_encoding(encoding):
    """Replace encoding name with normalised variant."""
    encoding = encoding.lower().replace('_', '-')
    try:
        # anything that's literally in the alias table
        return _ENCODING_ALIASES[encoding]
    except KeyError:
        pass
    # try replacements
    for start, replacement in _ENCODING_STARTSWITH.items():
        if encoding.startswith(start):
            encoding = replacement + encoding[len(start):]
            break
    # found in table after replacement?
    return _ENCODING_ALIASES.get(encoding, encoding)


def get_encoder(encoding_name, default=''):
    """Find an encoding by name and return codec."""
    encoding_name = encoding_name or default
    if encoding_name:
        encoding_name = normalise_encoding(encoding_name)
        if encoding_name == 'unicode':
            return Unicode()
        try:
            return _codepages[encoding_name]
            logging.debug(f'Using codepage `{encoding_name}`.')
        except LookupError as exc:
            logging.debug(exc)
            pass
        try:
            return PythonCodec(encoding_name)
            logging.debug(f'Using Python codec `{encoding_name}` as codepage.')
        except LookupError as exc:
            logging.debug(exc)
            pass
    # this will break some formats
    logging.debug('Unknown encoding `%s`.', encoding_name)
    return None


###################################################################################################
# read codepage from file

def load_codepage_file(filename, *, format='ucp', name=''):
    """Create new MapEncoder from file."""
    data = _get_data(filename)
    if not data:
        raise LookupError(f'No data in codepage file `{filename}`.')
    try:
        mapping = _mapping_from_data(data, **_FORMATS[format])
    except KeyError as exc:
        raise LookupError(f'Undefined codepage file format {format}.') from exc
    if not name:
        name = Path(filename).stem
    return MapEncoder(mapping, name)


def _mapping_from_data(data, *, comment, separator, joiner, codepoint_column, unicode_column):
    """Extract codepage mapping from file data (as bytes)."""
    mapping = {}
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        # strip off comments; split unicodepoint and hex string
        splitline = line.split(comment)[0].split(separator)
        # ignore malformed lines
        exc = ''
        if len(splitline) >= 2:
            try:
                cp_str, uni_str = splitline[codepoint_column], splitline[unicode_column]
                cp_str = cp_str.strip()
                uni_str = uni_str.strip()
                # right-to-left marker in mac codepages
                uni_str = uni_str.replace('<RL>+', '').replace('<LR>+', '')
                # multibyte code points given as single large number
                cp_point = tuple(int_to_bytes(int(cp_str, 16)))
                # allow sequence of unicode code points separated by 'joiner'
                mapping[cp_point] = ''.join(
                    chr(int(_substr, 16)) for _substr in uni_str.split(joiner)
                )
                continue
            except (ValueError, TypeError) as e:
                exc = str(e)
        logging.warning('Could not parse line in codepage file: %s [%s]', exc, repr(line))
    return mapping


def _get_data(filename):
    """Get package or fle data."""
    try:
        return pkgutil.get_data(__name__, filename)
    except EnvironmentError:
        # "If the package cannot be located or loaded, then None is returned." say the docs
        # but it seems to raise FileNotFoundError if the *resource* isn't there
        pass
    try:
        with open(filename, 'rb') as cpfile:
            return cpfile.read()
    except EnvironmentError:
        return None

def is_fullwidth(char):
    """Check if a character / grapheme sequence is fullwidth."""
    if not char:
        return False
    if len(char) > 1:
        # deal with combined glyphs
        return any(is_fullwidth(_c) for _c in char)
    return unicodedata.east_asian_width(char) in ('W', 'F')


###################################################################################################

class CodepageRegistry:
    """Register user-defined codepages."""

    # table of user-registered or -overridden codepages
    _registered = {}

    @classmethod
    def register(cls, name, filename, format='ucp'):
        """Override an existing codepage or register an unknown one."""
        name = normalise_encoding(name)
        cls._registered[name] = (filename, format)

    def __contains__(self, name):
        """Check if a name is defined in this registry."""
        return name in self._registered

    def __getitem__(self, name):
        """Get codepage from registry by name; raise LookupError if not found."""
        try:
            filename, format = self._registered[name]
        except KeyError as exc:
            raise LookupError(f'Codepage {name} not registered.') from exc
        return load_codepage_file(filename, name=name, format=format)

    def __repr__(self):
        """String representation."""
        return (
            'CodepageRegistry('
            + ('\n' if self._registered else '')
            + '\n    '.join(f"'{_k}': '{_v}'" for _k, _v in self._registered.items())
            + ')'
        )


###################################################################################################

class Encoder:
    """
    Convert between unicode and ordinals.
    Encoder objects act on single-glyph codes only, which may be single- or multi-codepoint.
    They need not encode/decode between full strings and bytes.
    """

    def __init__(self, name):
        """Set encoder name."""
        self.name = name

    def char(self, codepoint):
        """Convert codepoint to character, return empty string if missing."""
        raise NotImplementedError

    def codepoint(self, char):
        """Convert character to codepoint, return None if missing."""
        raise NotImplementedError

    def table(self, page=0):
        """Chart of page in codepage."""
        bg = '\u2591'
        cps = range(256)
        cps = (((page, _c) if page else (_c,)) for _c in cps)
        chars = (self.char(_cp) for _cp in cps)
        chars = ((_c if _c.isprintable() else '\ufffd') for _c in chars)
        chars = ((_c if is_fullwidth(_c) else ((_c + ' ') if _c else bg*2)) for _c in chars)
        chars = [*chars]
        return ''.join((
            '    ', ' '.join(f'_{_c:x}' for _c in range(16)), '\n',
            '  +', '-'*48, '-', '\n',
            '\n'.join(
                ''.join((f'{_r:x}_|', bg, bg.join(chars[16*_r:16*(_r+1)]), bg))
                for _r in range(16)
            )
        ))

    def __repr__(self):
        """Representation."""
        return (
            f"{type(self).__name__}(name='{self.name}' mapping=\n"
            + self.table()
            + '\n)'
        )


class PythonCodec(Encoder):
    """Convert between unicode and ordinals using a Python codec."""

    def __init__(self, encoding):
        """Set up codec."""
        # force early LookupError if not known
        try:
            b'x'.decode(encoding)
            'x'.encode(encoding)
        except Exception as exc:
            raise LookupError(f'Could not use Python codec `{encoding}` as codepage: {exc}.')
        super().__init__(encoding)
        self._encoding = encoding

    def char(self, codepoint):
        """Convert codepoint sequence to character, return empty string if missing."""
        byte_seq = bytes(codepoint)
        # ignore: return empty string if not found
        return byte_seq.decode(self._encoding, errors='ignore')

    def codepoint(self, char):
        """Convert character to codepoint sequence, return empty tuple if missing."""
        return tuple(char.encode(self._encoding, errors='ignore'))


class MapEncoder(Encoder):
    """Convert between unicode and ordinals using stored mapping."""

    def __init__(self, mapping, name):
        """Create codepage from a dictionary codepoint -> char."""
        if not mapping:
            name = ''
        super().__init__(name)
        # copy dict
        self._ord2chr = {**mapping}
        self._chr2ord = {_v: _k for _k, _v in self._ord2chr.items()}

    def char(self, codepoint):
        """Convert codepoint sequence to character, return empty string if missing."""
        codepoint = tuple(codepoint)
        if not all(isinstance(_i, int) for _i in codepoint):
            raise TypeError('Codepoint must be bytes or sequence of integers.')
        try:
            return self._ord2chr[codepoint]
        except KeyError as e:
            return ''

    def codepoint(self, char):
        """Convert character to codepoint sequence, return empty tuple if missing."""
        try:
            return self._chr2ord[char]
        except KeyError as e:
            return ()

    @property
    def mapping(self):
        return {**self._ord2chr}

    def __eq__(self, other):
        """Compare to other MapEncoder."""
        return (self._ord2chr == other._ord2chr)

    def __sub__(self, other):
        """Return encoding with only characters that differ from right-hand side."""
        return MapEncoder(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if other.char(_k) != _v},
            name=f'{self.name}-{other.name}'
        )


class Unicode(Encoder):
    """Convert between unicode and ordinals."""

    def __init__(self):
        """Unicode converter."""
        super().__init__('unicode')

    @staticmethod
    def char(codepoint):
        """Convert codepoint to character."""
        return ''.join(chr(_i) for _i in codepoint)

    @staticmethod
    def codepoint(char):
        """Convert character to codepoint."""
        # we used to normalise to NFC here, presumably to reduce multi-codepoint situations
        # but it leads to inconsistency between char and codepoint for canonically equivalent chars
        #char = unicodedata.normalize('NFC', char)
        return tuple(ord(_c) for _c in char)


###################################################################################################

_codepages = CodepageRegistry()

# ISO codepages
for _name, _file in _ISO_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'format_a')

# Adobe codepages
for _name, _file in _ADOBE_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'adobe')

# Apple codepages
for _name, _file in _APPLE_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'format_a')

# Microsoft codepages
for _name, _file in _MICROSOFT_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'format_a')

# miscellaneous codepages
for _name, (_file, _fmt) in _OTHER_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', _fmt)

# UCP codepages
for _file in resource_listdir(__name__, 'codepages/'):
    _codepages.register(Path(_file).stem, f'codepages/{_file}', 'ucp')
