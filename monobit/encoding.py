"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import pkgutil
import logging

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
        encoding_name = encoding_name.lower().replace('-', '_')
        if normalise_encoding(encoding_name) == 'unicode':
            return Unicode
        try:
            return Codepage(encoding_name)
        except LookupError:
            pass
        try:
            return Codec(encoding_name)
        except LookupError:
            pass
    # this will break some formats
    logging.debug('Unknown encoding `%s`.', encoding_name)
    return None


def _get_package_data(filename):
    """Get package data."""
    try:
        return pkgutil.get_data(__name__, filename)
    except EnvironmentError:
        # "If the package cannot be located or loaded, then None is returned." say the docs
        # but it seems to raise FileNotFoundError if the *resource* isn't there
        return None



class Codec:
    """Convert between unicode and ordinals using Python codec."""

    def __init__(self, encoding):
        """Set up codec."""
        # force early LookupError if not known
        b'x'.decode(encoding)
        'x'.encode(encoding)
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



class Codepage:
    """Convert between unicode and ordinals using stored codepage."""

    # table of user-registered or -overridden codepages
    _registered = {}

    def __init__(self, codepage_name):
        """Read a codepage file and convert to codepage dict."""
        codepage_name = codepage_name.lower().replace('_', '-')
        if codepage_name in self._registered:
            with open(self._registered[codepage_name], 'rb') as custom_cp:
                data = custom_cp.read()
            self._mapping = self._mapping_from_data(data, separator=':', codepoint_first=True)
        else:
            # Adobe codepages
            adobe_file = _ADOBE_ENCODINGS.get(codepage_name, '')
            apple_file = _APPLE_ENCODINGS.get(codepage_name, '')
            if adobe_file:
                data = _get_package_data(f'codepages/{adobe_file}')
                # split by whitespace, unicode is first data point
                self._mapping = self._mapping_from_data(data, separator=None, codepoint_first=False)
            elif apple_file:
                data = _get_package_data(f'codepages/{apple_file}')
                # split by whitespace, unicode is first data point
                self._mapping = self._mapping_from_data(data, separator=None, codepoint_first=True)
            else:
                # UCP codepages
                data = _get_package_data(f'codepages/{codepage_name}.ucp')
                self._mapping = self._mapping_from_data(data, separator=':', codepoint_first=True)
            if data is None:
                raise LookupError(codepage_name)
        self._inv_mapping = {_v: _k for _k, _v in self._mapping.items()}

    def _mapping_from_data(self, data, separator=':', codepoint_first=True):
        """Extract codepage mapping from file data (as bytes)."""
        mapping = {}
        for line in data.decode('utf-8-sig').splitlines():
            # ignore empty lines and comment lines (first char is #)
            if (not line) or (line[0] == '#'):
                continue
            # strip off comments; split unicodepoint and hex string
            splitline = line.split('#')[0].split(separator)
            # ignore malformed lines
            if len(splitline) < 2:
                continue
            try:
                if codepoint_first:
                    # UCP, Apple
                    # extract codepage point
                    cp_point = int(splitline[0].strip(), 16)
                    # UCP: allow sequence of code points separated by commas
                    mapping[cp_point] = ''.join(
                        chr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(',')
                    )
                else:
                    # Adobe format
                    cp_point = int(splitline[1].strip(), 16)
                    mapping[cp_point] = chr(int(splitline[0].strip(), 16))
            except (ValueError, TypeError):
                logging.warning('Could not parse line in codepage file: %s', repr(line))
        return mapping

    def chr(self, ordinal):
        """Convert ordinal to character, return empty string if missing."""
        try:
            return self._mapping[int(ordinal)]
        except (KeyError, TypeError) as e:
            return ''

    def ord(self, char):
        """Convert character to ordinal, return None if missing."""
        try:
            return self._inv_mapping[char]
        except KeyError as e:
            return None

    @classmethod
    def override(cls, name, filename):
        """Override an existing codepage or register an unknown one."""
        cls._registered[name] = filename


class Unicode:
    """Convert between unicode and ordinals."""

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
