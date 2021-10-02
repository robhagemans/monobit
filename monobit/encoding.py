"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import pkgutil
import logging
from pathlib import Path
import unicodedata

from pkg_resources import resource_listdir, resource_isdir

from .base.binary import int_to_bytes


_ENCODING_ALIASES = {
    'ucs': 'unicode',
    'iso10646': 'unicode',
    'iso10646-1': 'unicode',

    # X11 / BDF encoding names
    #'microsoft-symbol': '', # http://www.kostis.net/charsets/symbol.htm
    #'microsoft-win3.1': '', # is this the windows-3.1 version of 'windows-ansi'?

}


_ENCODING_FILES = {

    'format_a': {

        # iso standards
        # https://www.unicode.org/Public/MAPPINGS/ISO8859
        'iso-8859/8859-1.TXT': ('latin-1', 'iso8859-1', 'iso-ir-100', 'ibm-819'),
        'iso-8859/8859-2.TXT': ('latin-2', 'iso8859-2', 'iso-ir-101', 'ibm-1111'),
        'iso-8859/8859-3.TXT': ('latin-3', 'iso8859-3', 'iso-ir-109', 'ibm-913'),
        'iso-8859/8859-4.TXT': ('latin-4', 'iso8859-4', 'iso-ir-110', 'ibm-914'),
        'iso-8859/8859-5.TXT': ('iso8859-5', 'cyrillic', 'latin-cyrillic', 'iso-ir-144', 'ecma-113'),
        'iso-8859/8859-6.TXT': ('iso8859-6', 'arabic', 'latin-arabic', 'asmo-708', 'iso-ir-127', 'ecma-114'),
        'iso-8859/8859-7.TXT': ('iso8859-7', 'greek', 'latin-greek', 'greek8', 'iso-ir-126', 'ibm-813', 'elot-928', 'ecma-118'),
        'iso-8859/8859-8.TXT': ('iso8859-8', 'hebrew', 'latin-hebrew', 'iso-ir-138', 'ibm-916', 'ecma-121'),
        'iso-8859/8859-9.TXT': ('iso8859-9', 'latin-5', 'turkish', 'iso-ir-148', 'ibm-920', 'ecma-128'),
        'iso-8859/8859-10.TXT': ('iso8859-10', 'latin-6', 'ibm-919', 'iso-ir-157', 'ecma-144'),
        'iso-8859/8859-11.TXT': ('iso8859-11', 'latin-thai'),
        'iso-8859/8859-13.TXT': ('iso8859-13', 'latin-7', 'baltic-rim', 'ibm-921', 'iso-ir-179'),
        'iso-8859/8859-14.TXT': ('iso8859-14', 'latin-8', 'celtic', 'iso-celtic', 'iso-ir-199'),
        'iso-8859/8859-15.TXT': ('iso8859-15', 'latin-9', 'latin-0'),
        'iso-8859/8859-16.TXT': ('iso8859-16', 'latin-10', 'sr-14111', 'iso-ir-226'),

        # Windows codepages
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/WINDOWS
        # thai
        'microsoft/WINDOWS/CP874.TXT': ('windows-874', 'ibm-1162'),
        # japanese shift-jis
        'microsoft/WINDOWS/CP932.TXT': ('windows-932', 'windows-31j', 'cp943c', 'ibm-943', 'ms-kanji'),
        # simplified chinese gbk
        'microsoft/WINDOWS/CP936.TXT': ('windows-936', 'ibm-1386'),
        # korean extended wansung / unified hangul code
        'microsoft/WINDOWS/CP949.TXT': ('windows-949', 'ext-wansung', 'uhc', 'ibm-1363'),
        # traditional chinese big-5
        'microsoft/WINDOWS/CP950.TXT': ('windows-950', 'ms-big5'),
        # latin - central & eastern europe
        'microsoft/WINDOWS/CP1250.TXT': ('windows-1250', 'cp1250', 'ibm-1250'),
        # cyrillic
        'microsoft/WINDOWS/CP1251.TXT': ('windows-1251', 'cp1251', 'ibm-1251'),
        # latin - western europe
        'microsoft/WINDOWS/CP1252.TXT': ('windows-1252', 'ansi', 'ansinew', 'cp1252', 'ibm-1252'),
        # greek
        'microsoft/WINDOWS/CP1253.TXT': ('windows-1253', 'greek-ansi', 'cp1253', 'ibm-1253'),
        # latin - turkish
        'microsoft/WINDOWS/CP1254.TXT': ('windows-1254', 'cp1254', 'ibm-1254'),
        # hebrew
        'microsoft/WINDOWS/CP1255.TXT': ('windows-1255', 'cp1255', 'ibm-1255'),
        # arabic
        'microsoft/WINDOWS/CP1256.TXT': ('windows-1256', 'cp1256', 'ibm-1256'),
        # latin - baltic
        'microsoft/WINDOWS/CP1257.TXT': ('windows-1257', 'windows-baltic', 'cp1257', 'ibm-1257', 'lst-1590-3'),
        # latin - vietnamese
        'microsoft/WINDOWS/CP1258.TXT': ('windows-1258', 'cp1258', 'ibm-1258'),

        # IBM/OEM/MS-DOS codepages
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/PC
        'microsoft/PC/CP437.TXT': ('cp437', 'oem-437', 'ibm-437', 'oem-us', 'pc-8', 'dos-latin-us'),
        'microsoft/PC/CP737.TXT': ('cp737', 'oem-737', 'ibm-737', 'dos-greek'),
        'microsoft/PC/CP775.TXT': ('cp775', 'oem-775', 'ibm-775', 'dos-baltic-rim', 'lst-1590-1'),
        'microsoft/PC/CP850.TXT': ('cp850', 'oem-850', 'ibm-850', 'dos-latin-1'),
        'microsoft/PC/CP852.TXT': ('cp852', 'oem-852', 'ibm-852', 'dos-latin-2'),
        'microsoft/PC/CP855.TXT': ('cp855', 'oem-855', 'ibm-855', 'dos-cyrillic'),
        'microsoft/PC/CP857.TXT': ('cp857', 'oem-857', 'ibm-857', 'dos-turkish'),
        'microsoft/PC/CP860.TXT': ('cp860', 'oem-860', 'ibm-860', 'dos-portuguese'),
        'microsoft/PC/CP861.TXT': ('cp861', 'oem-861', 'ibm-861', 'cp-is', 'dos-icelandic'),
        'microsoft/PC/CP862.TXT': ('cp862', 'oem-862', 'ibm-862', 'dos-hebrew'),
        'microsoft/PC/CP863.TXT': ('cp863', 'oem-863', 'ibm-863', 'dos-french-canada'),
        'microsoft/PC/CP864.TXT': ('cp864', 'oem-864', 'ibm-864'), # dos-arabic
        'microsoft/PC/CP865.TXT': ('cp865', 'oem-865', 'ibm-865', 'dos-nordic'),
        'microsoft/PC/CP866.TXT': ('cp866', 'oem-866', 'ibm-866', 'dos-cyrillic-russian'),
        'microsoft/PC/CP869.TXT': ('cp869', 'oem-869', 'ibm-869', 'dos-greek2'),
        'microsoft/PC/CP874.TXT': ('ibm-874', 'ibm-9066'), # dos-thai

        # EBCDIC
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/EBCDIC
        'microsoft/PC/CP037.TXT': ('cp037', 'ibm037', 'ebcdic-cp-us', 'ebcdic-cp-ca', 'ebcdic-cp-wt', 'ebcdic-cp-nl'),
        'microsoft/PC/CP500.TXT': ('cp500', 'ibm500', 'ebcdic-international'),
        'microsoft/PC/CP875.TXT': ('cp875', 'ibm875'),
        'microsoft/PC/CP1026.TXT': ('cp1026', 'ibm1026'),

        # Apple codepages matching a script code
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/
        #
        #'mac-roman': 'apple/ROMAN.TXT',
        # this has the pre-euro version of the mac-roman set (aka microsoft's cp 10000)
        'microsoft/MAC/ROMAN.TXT': ('mac-roman', 'mac', 'macintosh'),
        'apple/JAPANESE.TXT': ('mac-japanese',),
        'apple/CHINTRAD.TXT': ('mac-trad-chinese',),
        'apple/KOREAN.TXT': ('mac-korean',),
        'apple/ARABIC.TXT': ('mac-arabic',),
        'apple/HEBREW.TXT': ('mac-hebrew',),
        'apple/GREEK.TXT': ('mac-greek',),
        # note: A2, B6, FF changed after mac-os 9.0
        # see https://en.wikipedia.org/wiki/Mac_OS_Cyrillic_encoding
        'apple/CYRILLIC.TXT': ('mac-cyrillic',),
        'apple/DEVANAGA.TXT': ('mac-devanagari',),
        'apple/GURMUKHI.TXT': ('mac-gurmukhi',),
        'apple/GUJARATI.TXT': ('mac-gujarati',),
        'apple/THAI.TXT': ('mac-thai',) ,
        'apple/CHINSIMP.TXT': ('mac-simp-chinese',),
        # "non-cyrillic slavic", mac-centeuro
        # cf. 'microsoft/MAC/LATIN2.TXT'
        'apple/CENTEURO.TXT': ('mac-centraleurope', 'mac-ce', 'mac-latin2', 'mac-centeuro', 'mac-east-eur-roman'),
        # Armenian and Georgian taken from Evertype:
        # https://www.evertype.com/standards/mappings/
        'evertype/GEORGIAN.TXT': ('mac-georgian',),
        'evertype/ARMENIAN.TXT': ('mac-armenian',),
        # Apple codepages not matching a script code
        'apple/CELTIC.TXT': ('mac-celtic',),
        'apple/CROATIAN.TXT': ('mac-croatian',),
        'apple/DINGBATS.TXT': ('mac-dingbats',),
        'apple/FARSI.TXT': ('mac-farsi',),
        'apple/GAELIC.TXT': ('mac-gaelic',),
        'apple/ICELAND.TXT': ('mac-icelandic',),
        'apple/INUIT.TXT': ('mac-inuit',),
        'apple/SYMBOL.TXT': ('mac-symbol',),
        'apple/TURKISH.TXT': ('mac-turkish',),
        'apple/UKRAINE.TXT': ('mac-ukrainian',),
        # Apple scripts for which no codepage found
        # note - Gurmukhi and Gujarati are ISCII-based
        # so can we infer the other Indic scripts that have an ISCII?
        #'mac-oriya':
        #'mac-bengali':
        #'mac-tamil':
        #'mac-telugu':
        #'mac-kannada':
        #'mac-malayalam':
        #'mac-sinhalese':
        #'mac-burmese':
        #'mac-khmer':
        #'mac-laotian':
        #'mac-tibetan':
        #'mac-mongolian':
        #'mac-ethiopic', # alias: 'mac-geez'
        #'mac-vietnamese':
        #'mac-sindhi' # alias 'mac-ext-arabic'

        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/
        # cyrillic
        'misc/KOI8-R.TXT': ('koi8-r', 'cp878'),
        'misc/KOI8-U.TXT': ('koi8-u',),
        # hebrew
        'misc/CP424.TXT': ('cp424', 'ebcdic-hebrew'),
        'misc/CP856.TXT': ('cp856', 'oem-856', 'ibm-856'),
        # arabic - urdu
        'misc/CP1006.TXT': ('cp1006', 'ibm-1006'),
        # APL
        'misc/APL-ISO-IR-68.TXT': ('iso-ir-68',) ,
        # korean
        'misc/KPS9566.TXT': ('kps-9566', 'iso-ir-202'),
        # cyrillic - kazakh
        'misc/KZ1048.TXT': ('kz-1048', 'strk1048-2002', 'rk-1048'),

        # not loaded from misc/:
        # SGML.TXT
        # US-ASCII-QUOTES.TXT
        'misc/ATARIST.TXT': ('atari-st',),
        'misc/NEXTSTEP.TXT': ('next', 'nextstep', 'next-multinational') ,
        'misc/GSM0338.TXT': ('gsm-03.38', 'gsm'),

        # Roman Czyborra's codepage tables
        # cyrillic pages
        'czyborra/koi-0.txt': ('koi0', 'gost-13052'),
        'czyborra/koi-7.txt': ('koi7', 'gost-19768-74-7'),
        # koi-8 should be overlaid with ascii
        'czyborra/koi8-a.txt': ('koi8-a', 'koi8', 'gost-19768-74-8'),
        'czyborra/koi8-b.txt': ('koi8-b',),
        'czyborra/koi8-f.txt': ('koi8-f', 'koi8-unified'),
        'czyborra/koi8-e.txt': ('koi8-e', 'iso-ir-111', 'ecma-cyrillic'),
        'czyborra/gost19768-87.txt': ('gost-19768-87',) ,
        # use unicode.org misc/ mappings for KOI8-U and KOI8-U
        # 'koi8-r': 'czyborra/koi-8-e.txt',
        # 'koi8-u': 'czyborra/koi-8-e.txt',
        # use unicode.org microsoft/ mappings for cp866
        # 'cp866': 'czyborra/cp866.txt',
        'czyborra/bulgarian-mik.txt': ('mik', 'bulgarian-mik', 'bulgaria-pc'),
        # latin pages
        'czyborra/hp-roman8.txt': ('hp-roman8', 'ibm-1051'),
        'czyborra/viscii.corrected.txt': ('viscii',),
        'czyborra/vn5712-1.txt': ('tcvn5712-1', 'vscii-1'),
        'czyborra/vn5712-2.txt': ('tcvn5712-2', 'vscii-2'),

        # mleisher's csets
        'mleisher/ALTVAR.TXT' : ('alternativnyj-variant', 'alternativnyj', 'av'),
        'mleisher/ARMSCII-7.TXT' : ('armscii-7',),
        'mleisher/ARMSCII-8.TXT' : ('armscii-8',),
        'mleisher/ARMSCII-8A.TXT' : ('armscii-8a',),
        'mleisher/DECMCS.TXT' : ('dec-mcs', 'dmcs', 'mcs', 'ibm-1100', 'cp1100'),
        'mleisher/GEO-ITA.TXT' : ('georgian-academy', 'georgian-ita'),
        'mleisher/GEO-PS.TXT' : ('georgian-parliament', 'georgian-ps'),
        'mleisher/IRANSYSTEM.TXT' : ('iran-system', 'iransystem'),
        'mleisher/KOI8RU.TXT' : ('koi8-ru',),
        'mleisher/OSNOVAR.TXT' : ('osnovnoj-variant', 'osnovnoj', 'ov'),
        'mleisher/RISCOS.TXT' : ('risc-os', 'acorn-risc-os'),
        'mleisher/TIS620.TXT' : ('tis-620',),
    },

    'adobe': {
        # Adobe encodings
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/ADOBE/
        'adobe/stdenc.txt': ('adobe-standard',),
        'adobe/symbol.txt': ('adobe-symbol',),
        'adobe/zdingbat.txt': ('adobe-dingbats',),

        # IBM PC memory-mapped video graphics, overlaying the control character range
        # to be used in combination with other code pages e.g. cp437
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/
        'misc/IBMGRAPH.TXT': ('ibm-graphics',),
    },

    'ucm': {
        # charmaps from Keld Simonsen (dkuug)
        'dkuug/iso646-us': ('ascii', 'iso646-us', 'ascii-0', 'us-ascii', 'iso-ir-6', 'ansi-x3.4-1968'),
        'dkuug/iso646-ca': ('iso646-ca', 'iso-ir-121', 'csa7-1'),
        'dkuug/iso646-ca2': ('iso646-ca2', 'iso-ir-122', 'csa7-2'),
        'dkuug/iso646-cn': ('iso646-cn', 'iso-ir-57', 'gbt-1988-80'),
        'dkuug/iso646-de': ('iso646-de', 'iso-ir-21', 'din-66003'),
        'dkuug/iso646-dk': ('iso646-dk', 'ds-2089'),
        'dkuug/iso646-es': ('iso646-es', 'iso-ir-17'),
        'dkuug/iso646-es2': ('iso646-es2', 'iso-ir-85'),
        'dkuug/iso646-fr': ('iso646-fr', 'iso-ir-69'),
        'dkuug/iso646-gb': ('iso646-gb', 'iso-ir-4', 'bs-4730'),
        'dkuug/iso646-hu': ('iso646-hu', 'iso-ir-86', 'msz7795-3'),
        'dkuug/iso646-it': ('iso646-it', 'iso-ir-15', 'uni-0204-70'),
        'dkuug/iso646-jp': ('iso646-jp', 'iso-ir-14', 'jiscii', 'jis-roman', 'ibm-895'),
        'dkuug/iso646-kr': ('iso646-kr',),
        'dkuug/iso646-yu': ('iso646-yu', 'iso-ir-141', 'yuscii-latin', 'croscii', 'sloscii', 'jus-i.b1.002'),
        # ibm-897 extends jis-x0201
        'dkuug/jis_x0201': ('jis-x0201', 'jis-c-6220'),
        'dkuug/x0201-7': ('x0201-7', 'iso-ir-13'),

        # charmaps from IBM/Unicode ICU project
        'icu/ibm-1125_P100-1997.ucm': ('ruscii', 'ibm-1125', 'cp866u', 'cp866nav'),
        'icu/ibm-720_P100-1997.ucm': ('cp720', 'ibm-720', 'transparent-asmo'),
        'icu/ibm-858_P100-1997.ucm': ('cp858', 'ibm-858', 'cp850-euro'),
        'icu/ibm-868_P100-1995.ucm': ('cp868', 'ibm-868', 'cp-ar', 'dos-urdu'),
    },

    'kostis': {
        # Kosta Kostis's codepage tables
        'kostis/851.txt': ('cp851',),
        'kostis/853.corrected.txt': ('cp853',),
    },

    'ucp': {
        # manually constructed based on gif images
        # https://web.archive.org/web/20061017214053/http://www.cyrillic.com/ref/cyrillic/
        'manual/russup3.ucp': ('dos-russian-support-3', 'rs3', 'russup3'),
        'manual/russup4ac.ucp': ('dos-russian-support-4-academic', 'rs4ac', 'russup4ac'),
        'manual/russup4na.ucp': ('dos-russian-support-4', 'rs4', 'russup4na'),
    }
}

# codepages to be overlaid with IBM graphics in range 0x00--0x1f and 0x7f
_ASCII_RANGE = tuple((_cp,) for _cp in range(0x80))
_IBM_GRAPH_RANGE = tuple((_cp,) for _cp in range(0x20)) + ((0x7f,),)
_IBM_OVERLAYS = (
    'cp437', 'cp720', 'cp737', 'cp775',
    'cp850', 'cp851', 'cp852', 'cp853', 'cp855', 'cp856', 'cp857', 'cp858',
    'cp860', 'cp861', 'cp862', 'cp863', 'cp865', 'cp866', 'cp868', 'cp869', # not cp864
    'cp874',
    'windows-950',
    'mik', 'koi8-r', 'koi8-u', 'koi8-ru', 'ruscii', 'rs3', 'rs4', 'rs4ac',
)
_ASCII_OVERLAYS = (
    'koi8-a', 'koi8-b', 'koi8-e', 'koi8-f', 'gost-19768-87', 'mik',
    # per NEXTSTEP.TXT, identical to ascii.
    # wikipedia suggests it's us-ascii-quotes
    'next', 'rs3', 'rs4', 'rs4ac',
)


# replacement patterns for normalisation
_ENCODING_STARTSWITH = {
    'microsoft-cp': 'windows-',
    'ms-': 'windows-',
    'ibm-cp': 'ibm-',
    'apple-': 'mac-',
    # mac-roman also known as x-mac-roman etc.
    'x-': '',
    'iso-': 'iso',
    'ms-dos-': 'dos-',
    'koi-': 'koi',
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
        try:
            return _codepages[encoding_name]
            logging.debug(f'Using codepage `{encoding_name}`.')
        except LookupError as exc:
            logging.warning('Could not use encoding `%s`: %s', encoding_name, exc)
    # this will break some formats
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
# read codepage from file

def load_codepage_file(filename, *, format='ucp', name=''):
    """Create new MapEncoder from file."""
    try:
        data = pkgutil.get_data(__name__, filename)
    except EnvironmentError as exc:
        raise LookupError(f'Could not load codepage file `{filename}`: {exc}')
    if not data:
        raise LookupError(f'No data in codepage file `{filename}`.')
    try:
        reader, kwargs = _FORMATS[format]
        mapping = reader(data, **kwargs)
    except KeyError as exc:
        raise LookupError(f'Undefined codepage file format {format}.') from exc
    if not name:
        name = Path(filename).stem
    return MapEncoder(mapping, name)


def _from_text_columns(
        data, *, comment, separator, joiner, codepoint_column, unicode_column,
        codepoint_base=16, unicode_base=16, inline_comments=True
    ):
    """Extract codepage mapping from text columns in file data (as bytes)."""
    mapping = {}
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        # strip off comments
        if inline_comments:
            line = line.split(comment)[0]
        # split unicodepoint and hex string
        splitline = line.split(separator)
        if len(splitline) > max(codepoint_column, unicode_column):
            cp_str, uni_str = splitline[codepoint_column], splitline[unicode_column]
            cp_str = cp_str.strip()
            uni_str = uni_str.strip()
            # right-to-left marker in mac codepages
            uni_str = uni_str.replace('<RL>+', '').replace('<LR>+', '')
            # czyborra's codepages have U+ in front
            if uni_str.upper().startswith('U+'):
                uni_str = uni_str[2:]
            # czyborra's codepages have = in front
            if cp_str.upper().startswith('='):
                cp_str = cp_str[1:]
            try:
                # multibyte code points given as single large number
                cp_point = tuple(int_to_bytes(int(cp_str, codepoint_base)))
                # allow sequence of unicode code points separated by 'joiner'
                char = ''.join(
                    chr(int(_substr, unicode_base))
                    for _substr in uni_str.split(joiner)
                )
                if char != '\uFFFD':
                    # u+FFFD replacement character is used to mark undefined code points
                    mapping[cp_point] = char
            except (ValueError, TypeError) as e:
                # ignore malformed lines
                logging.warning('Could not parse line in codepage file: %s [%s]', e, repr(line))
    return mapping


def _from_ucm_charmap(data):
    """Extract codepage mapping from ucm / linux charmap file data (as bytes)."""
    # only deals with sbcs
    comment = '#'
    escape = '\\'
    # precision indicator
    precision = '|'
    mapping = {}
    parse = False
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('<comment_char>'):
            comment = line.split()[-1].strip()
        elif line.startswith('<escape_char>'):
            escape = line.split()[-1].strip()
        elif line.startswith('CHARMAP'):
            parse = True
            continue
        elif line.startswith('END CHARMAP'):
            parse = False
        if not parse:
            continue
        # split columns
        splitline = line.split()
        # ignore malformed lines
        exc = ''
        cp_str, uni_str = '', ''
        for item in splitline:
            if item.startswith('<U'):
                # e.g. <U0000>
                uni_str = item[2:-1]
            elif item.startswith(escape + 'x'):
                cp_str = item[2:]
            elif item.startswith(precision):
                # precision indicator
                # |0 - A “normal”, roundtrip mapping from a Unicode code point and back.
                # |1 - A “fallback” mapping only from Unicode to the codepage, but not back.
                # |2 - A subchar1 mapping. The code point is unmappable, and if a substitution is performed, then the subchar1 should be used rather than the subchar. Otherwise, such mappings are ignored.
                # |3 - A “reverse fallback” mapping only from the codepage to Unicode, but not back to the codepage.
                # |4 - A “good one-way” mapping only from Unicode to the codepage, but not back.
                if item[1:].strip() != '0':
                    # only accept 'normal' mappings
                    # should we also allow "reverse fallback" ?
                    continue
            else:
                # ignore lines that start with anything else
                # this like <code_set_name>, CHARSET, END CHARSET
                continue
        if not uni_str or not cp_str:
            logging.warning('Could not parse line in codepage file: %s.', repr(line))
            continue
        cp_point = (int(cp_str, 16),)
        if cp_point in mapping:
            logging.debug('Ignoring redefinition of code point %s', cp_point)
        else:
            mapping[cp_point] = chr(int(uni_str, 16))
    return mapping

# codepage file format parameters
_FORMATS = {
    'ucp': (_from_text_columns, dict(
        comment='#', separator=':', joiner=',', codepoint_column=0, unicode_column=1
    )),
    'adobe': (_from_text_columns, dict(
        comment='#', separator='\t', joiner=None, codepoint_column=1, unicode_column=0
    )),
    'format_a': (_from_text_columns, dict(
    comment='#', separator=None, joiner='+', codepoint_column=0, unicode_column=1
    )),
    'ibmgraph_864': (_from_text_columns, dict(
        comment='#', separator='\t', joiner=None, codepoint_column=2, unicode_column=0
    )),
    'kostis': (_from_text_columns, dict(
        comment='#', separator='\t', joiner='+', codepoint_column=0, unicode_column=3,
        codepoint_base=16, unicode_base=10, inline_comments=False
    )),
    'ucm': (_from_ucm_charmap, {}),
}


###################################################################################################

class CodepageRegistry:
    """Register user-defined codepages."""

    # table of user-registered or -overridden codepages
    _registered = {}
    _overlays = {}

    @classmethod
    def register(cls, name, filename, format='ucp'):
        """Register a file to be loaded for a given codepage."""
        name = normalise_encoding(name)
        cls._registered[name] = (filename, format)

    @classmethod
    def overlay(cls, name, filename, overlay_range, format='ucp'):
        """Overlay a given codepage with an additional file."""
        name = normalise_encoding(name)
        try:
            cls._overlays[name].append((filename, format, overlay_range))
        except KeyError:
            cls._overlays[name] = [(filename, format, overlay_range)]

    def __iter__(self):
        """Iterate over names of registered codepages."""
        return iter(self._registered)

    def __getitem__(self, name):
        """Get codepage from registry by name; raise LookupError if not found."""
        name = normalise_encoding(name)
        if name == 'unicode':
            return Unicode()
        try:
            filename, format = self._registered[name]
        except KeyError as exc:
            raise LookupError(f'Codepage {name} not registered.') from exc
        codepage = load_codepage_file(filename, name=name, format=format)
        for filename, format, ovr_rng in self._overlays.get(name, ()):
            overlay = load_codepage_file(filename, format=format)
            codepage = codepage.overlay(overlay, ovr_rng)
        return codepage

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
        return isinstance(other, MapEncoder) and (self._ord2chr == other._ord2chr)

    def __sub__(self, other):
        """Return encoding with only characters that differ from right-hand side."""
        return MapEncoder(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if other.char(_k) != _v},
            name=f'[{self.name}]-[{other.name}]'
        )

    def __add__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        mapping = {**self.mapping}
        mapping.update(other.mapping)
        return MapEncoder(mapping=mapping, name=f'{self.name}')

    def take(self, codepoint_range):
        """Return encoding only for given range of codepoints."""
        return MapEncoder(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if _k in codepoint_range},
            name=f'subset[{self.name}]'
        )

    def overlay(self, other, codepoint_range):
        """Return encoding overlaid with all characters in the overlay range taken from rhs."""
        return self + other.take(codepoint_range)


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

    def __repr__(self):
        """Representation."""
        return type(self).__name__ + '()'


###################################################################################################

_codepages = CodepageRegistry()

# charmap files
for _format, _files in _ENCODING_FILES.items():
    for _file, _aliases in _files.items():
        _name = _aliases[0]
        _codepages.register(_name, f'codepages/{_file}', _format)
        for _alias in _aliases:
            if _alias in _ENCODING_ALIASES:
                logging.error(
                    'Character set alias collision: %s: %s or %s',
                    _alias, _name, _ENCODING_ALIASES[_alias]
                )
            _ENCODING_ALIASES[_alias] = _name

# overlays
for _name in _ASCII_OVERLAYS:
    _codepages.overlay(_name, 'codepages/iso-8859/8859-1.TXT', _ASCII_RANGE, 'format_a')
for _name in _IBM_OVERLAYS:
    _codepages.overlay(_name, 'codepages/misc/IBMGRAPH.TXT', _IBM_GRAPH_RANGE, 'adobe')
# second column in IBMGRAPH.TXT is there specially for this codepage
_codepages.overlay('cp864', 'codepages/misc/IBMGRAPH.TXT', _IBM_GRAPH_RANGE, 'ibmgraph_864')


# UCP codepages
for _file in resource_listdir(__name__, 'codepages/'):
    if not resource_isdir(__name__, _file):
        _codepages.register(Path(_file).stem, f'codepages/{_file}', 'ucp')
