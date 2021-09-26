"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

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


class Codec:
    """Convert between unicode and ordinals using python codec."""

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
