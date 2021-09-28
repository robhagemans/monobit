"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import pkgutil
import logging
from pathlib import Path

from pkg_resources import resource_listdir


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
}

# replacement patterns
_ENCODING_STARTSWITH = {
    'microsoft-cp': 'windows-',
    'ibm-cp': 'cp',
    'apple-': 'mac-',
    'x-mac-': 'mac-',
}

# official Adobe mapping files from
# https://www.unicode.org/Public/MAPPINGS/VENDORS/ADOBE/
_ADOBE_ENCODINGS = {
    'adobe-standard': 'adobe/stdenc.txt',
    'adobe-symbol': 'adobe/symbol.txt',
    'adobe-dingbats': 'adobe/zdingbat.txt',
}

# https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/
# also known as x-mac-roman etc.
_APPLE_ENCODINGS = {
    'mac-roman': 'apple/ROMAN.TXT',
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
    #'mac-georgian':
    #'mac-armenian':
    'mac-simp-chinese': 'apple/CHINSIMP.TXT',
    #'mac-tibetan':
    #'mac-mongolian':
    #'mac-ethiopian',
    'mac-centraleurope': 'apple/CENTEURO.TXT', # "non-cyrillic slavic", mac-centeuro
    #'mac-vietnamese':
    #'mac-sindhi':

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
}



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


###################################################################################################

class CodepageRegistry:
    """Register user-defined codepages."""

    # table of user-registered or -overridden codepages
    _registered = {}

    # codepage file format parameters
    _formats = {
        'ucp': dict(comment='#', separator=':', joiner=',', codepoint_first=True),
        'adobe': dict(comment='#', separator='\t', joiner=None, codepoint_first=True),
        'apple': dict(comment='#', separator=None, joiner='+', codepoint_first=True),
    }

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
        data = _get_data(filename)
        if not data:
            raise LookupError(f'No data in codepage file `{filename}` registered for {name}.')
        try:
            mapping = self._mapping_from_data(data, **self._formats[format])
        except KeyError as exc:
            raise LookupError(f'Undefined codepage file format {format}.') from exc
        return MapEncoder(mapping, name)

    def __repr__(self):
        """String representation."""
        return (
            'CodepageRegistry('
            + ('\n' if self._registered else '')
            + '\n    '.join(f"'{_k}': '{_v}'" for _k, _v in self._registered.items())
            + ')'
        )

    def _mapping_from_data(self, data, *, comment, separator, joiner, codepoint_first):
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
                    if codepoint_first:
                        cp_str, uni_str = splitline[0], splitline[1]
                    else:
                        uni_str, cp_str = splitline[0], splitline[1]
                    cp_str = cp_str.strip()
                    uni_str = uni_str.strip()
                    # right-to-left marker in mac codepages
                    uni_str = uni_str.replace('<RL>+', '').replace('<LR>+', '')
                    cp_point = int(cp_str, 16)
                    # allow sequence of code points separated by 'joiner'
                    mapping[cp_point] = ''.join(
                        chr(int(_substr, 16)) for _substr in uni_str.split(joiner)
                    )
                    continue
                except (ValueError, TypeError) as e:
                    exc = str(e)
            logging.warning('Could not parse line in codepage file: %s [%s]', exc, repr(line))
        return mapping


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

    def chr(self, ordinal):
        """Convert ordinal to character, return empty string if missing."""
        raise NotImplemented

    def ord(self, char):
        """Convert character to ordinal, return None if missing."""
        raise NotImplemented

    def chart(self, page=0):
        """Chart of page in codepage."""
        chars = [self.chr(256*page+_i) or ' ' for _i in range(256)]
        chars = ''.join((_c if _c.isprintable() else '\ufffd') for _c in chars)
        return (
            '    ' + ' '.join(f'_{_c:x}' for _c in range(16)) + '\n'
            + '\n'.join(
                f'{_r:x}_   ' + '  '.join(
                    chars[16*_r:16*(_r+1)]
                )
                for _r in range(16)
            )
        )

    def __repr__(self):
        """Representation."""
        return (
            f"<{type(self).__name__} name='{self.name}' mapping=\n"
            + self.chart()
            + '\n>'
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

    def chr(self, ordinal):
        """Convert ordinal to character, return empty string if missing."""
        if ordinal is None:
            return ''
        byte = bytes([int(ordinal)])
        # ignore: return empty string if not found
        char = byte.decode(self._encoding, errors='ignore')
        return char

    def ord(self, char):
        """Convert character to ordinal, return None if missing."""
        byte = char.encode(self._encoding, errors='ignore')
        if not byte:
            return None
        return byte[0]


class MapEncoder(Encoder):
    """Convert between unicode and ordinals using stored mapping."""

    def __init__(self, mapping, name):
        """Create codepage from a dictionary ord -> chr."""
        if not mapping:
            raise LookupError(name)
        super().__init__(name)
        # copy dict
        self._ord2chr = {**mapping}
        self._chr2ord = {_v: _k for _k, _v in self._ord2chr.items()}

    def chr(self, ordinal):
        """Convert ordinal to character, return empty string if missing."""
        try:
            return self._ord2chr[int(ordinal)]
        except (KeyError, TypeError) as e:
            return ''

    def ord(self, char):
        """Convert character to ordinal, return None if missing."""
        try:
            return self._chr2ord[char]
        except KeyError as e:
            return None


class Unicode(Encoder):
    """Convert between unicode and ordinals."""

    def __init__(self):
        """Unicode converter."""
        super().__init__('unicode')

    @staticmethod
    def chr(ordinal):
        """Convert ordinal to character."""
        if ordinal is None:
            return ''
        return chr(int(ordinal))

    @staticmethod
    def ord(char):
        """Convert character to ordinal."""
        # we used to normalise to NFC here, presumably to reduce multi-codepoint situations
        # but it leads to inconsistency between char and codepoint for canonically equivalent chars
        #char = unicodedata.normalize('NFC', char)
        if len(char) != 1:
            # empty chars or multi-codepoint grapheme clusters are not supported here
            return None
        return ord(char)


###################################################################################################

_codepages = CodepageRegistry()

# Adobe codepages
for _name, _file in _ADOBE_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'adobe')

# Apple codepages
for _name, _file in _APPLE_ENCODINGS.items():
    _codepages.register(_name, f'codepages/{_file}', 'apple')

# UCP codepages
for _file in resource_listdir(__name__, 'codepages/'):
    _codepages.register(Path(_file).stem, f'codepages/{_file}', 'ucp')
