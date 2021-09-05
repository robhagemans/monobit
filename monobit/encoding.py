"""
monobit.encoding - unicode encodings

(c) 2020 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
import pkgutil
import logging

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


def get_encoding(enc):
    """Find an encoding by name."""
    if enc:
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



class Codec:
    """Convert between unicode and ordinals using python codec."""

    def __init__(self, encoding):
        """Set up codec."""
        # force early LookupError if not known
        b'x'.decode(encoding)
        'x'.encode(encoding)
        self._encoding = encoding

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode, return empty string if missing."""
        byte = bytes([int(ordinal)])
        # ignore: return empty string if not found
        unicode = byte.decode(self._encoding, errors='ignore')
        return unicode

    def unicode_to_ord(self, unicode):
        """Convert unicode to ordinal, raise ValueError if missing."""
        byte = unicode.encode(self._encoding, errors='ignore')
        if not byte:
            return None
        return byte[0]



class Codepage:
    """Convert between unicode and ordinals."""

    # table of user-registered or -overridden codepages
    _registered = {}

    def __init__(self, codepage_name):
        """Read a codepage file and convert to codepage dict."""
        codepage_name = codepage_name.lower().replace('_', '-')
        if codepage_name in self._registered:
            with open(self._registered[codepage_name], 'rb') as custom_cp:
                data = custom_cp.read()
        else:
            try:
                data = pkgutil.get_data(__name__, 'codepages/{}.ucp'.format(codepage_name))
            except EnvironmentError:
                # "If the package cannot be located or loaded, then None is returned." say the docs
                # but it seems to raise FileNotFoundError if the *resource* isn't there
                data = None
            if data is None:
                raise LookupError(codepage_name)
        self._mapping = self._mapping_from_ucp_data(data)
        self._inv_mapping = {_v: _k for _k, _v in self._mapping.items()}

    def _mapping_from_ucp_data(self, data):
        """Extract codepage mapping from ucp file data (as bytes)."""
        mapping = {}
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
                mapping[cp_point] = ''.join(
                    chr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(',')
                )
            except (ValueError, TypeError):
                logging.warning('Could not parse line in codepage file: %s', repr(line))
        return mapping

    def ord_to_unicode(self, ordinal):
        """Convert ordinal to unicode, return empty string if missing."""
        try:
            return self._mapping[int(ordinal)]
        except KeyError as e:
            return ''

    def unicode_to_ord(self, unicode):
        """Convert unicode to ordinal, return None if missing."""
        try:
            return self._inv_mapping[unicode]
        except KeyError as e:
            return None

    @classmethod
    def override(cls, name, filename):
        """Override an existing codepage or register an unknown one."""
        cls._registered[name] = filename


class Unicode:
    """Convert between unicode and ordinals."""

    @staticmethod
    def ord_to_unicode(ordinal):
        """Convert ordinal to unicode."""
        return chr(int(ordinal))

    @staticmethod
    def unicode_to_ord(unicode):
        """Convert unicode to ordinal."""
        unicode = unicodedata.normalize('NFC', unicode)
        if len(unicode) != 1:
            # empty chars or multi-codepoint grapheme clusters are not supported here
            return None
        return ord(unicode)


class NoEncoding:

    @staticmethod
    def ord_to_unicode(ordinal):
        return ''

    @staticmethod
    def unicode_to_ord(key):
        return None
