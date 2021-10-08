"""
monobit.encoding - unicode encodings

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import pkgutil
import logging
from pathlib import Path
import unicodedata
from html.parser import HTMLParser
import binascii

from pkg_resources import resource_listdir, resource_isdir

from .base.binary import int_to_bytes


_ENCODING_FILES = (

    ('txt', {}, (
        # iso standards
        # https://www.unicode.org/Public/MAPPINGS/ISO8859
        ('iso-8859/8859-1.TXT', 'latin-1', 'iso8859-1', 'iso-ir-100', 'ibm-819'),
        ('iso-8859/8859-2.TXT', 'latin-2', 'iso8859-2', 'iso-ir-101', 'ibm-1111'),
        ('iso-8859/8859-3.TXT', 'latin-3', 'iso8859-3', 'iso-ir-109', 'ibm-913'),
        ('iso-8859/8859-4.TXT', 'latin-4', 'iso8859-4', 'iso-ir-110', 'ibm-914'),
        ('iso-8859/8859-5.TXT', 'iso8859-5', 'cyrillic', 'latin-cyrillic', 'iso-ir-144', 'ecma-113'),
        ('iso-8859/8859-6.TXT', 'iso8859-6', 'arabic', 'latin-arabic', 'asmo-708', 'iso-ir-127', 'ecma-114'),
        ('iso-8859/8859-7.TXT', 'iso8859-7', 'greek', 'latin-greek', 'greek8', 'iso-ir-126', 'ibm-813', 'elot-928', 'ecma-118'),
        ('iso-8859/8859-8.TXT', 'iso8859-8', 'hebrew', 'latin-hebrew', 'iso-ir-138', 'ibm-916', 'ecma-121'),
        ('iso-8859/8859-9.TXT', 'iso8859-9', 'latin-5', 'turkish', 'iso-ir-148', 'ibm-920', 'ecma-128'),
        ('iso-8859/8859-10.TXT', 'iso8859-10', 'latin-6', 'ibm-919', 'iso-ir-157', 'ecma-144'),
        # differs from tis-620 only in a code point mapping NBSP
        ('iso-8859/8859-11.TXT', 'iso8859-11', 'latin-thai'),
        ('iso-8859/8859-13.TXT', 'iso8859-13', 'latin-7', 'baltic-rim', 'ibm-921', 'iso-ir-179'),
        ('iso-8859/8859-14.TXT', 'iso8859-14', 'latin-8', 'celtic', 'iso-celtic', 'iso-ir-199'),
        ('iso-8859/8859-15.TXT', 'iso8859-15', 'latin-9', 'latin-0'),
        ('iso-8859/8859-16.TXT', 'iso8859-16', 'latin-10', 'sr-14111', 'iso-ir-226'),

        # Windows codepages
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/WINDOWS
        # thai
        # tis620-2 is the name used in xorg
        # the xorg encoding also adds some PUA mappings on undefined code points
        ('microsoft/WINDOWS/CP874.TXT', 'windows-874', 'ibm-1162', 'tis620-2'),
        # japanese shift-jis
        ('microsoft/WINDOWS/CP932.TXT', 'windows-932', 'windows-31j', 'cp943c', 'ibm-943', 'ms-kanji', 'windows-shift-jis'),
        # simplified chinese gbk
        # use more extensive version from icu by default
        #'microsoft/WINDOWS/CP936.TXT', 'windows-936', 'ibm-1386'),
        # korean extended wansung / unified hangul code
        ('microsoft/WINDOWS/CP949.TXT', 'windows-949', 'ext-wansung', 'uhc', 'ibm-1363'),
        # traditional chinese big-5
        ('microsoft/WINDOWS/CP950.TXT', 'windows-950', 'ms-big5'),
        # latin - central & eastern europe
        ('microsoft/WINDOWS/CP1250.TXT', 'windows-1250', 'cp1250', 'ibm-1250'),
        # cyrillic
        ('microsoft/WINDOWS/CP1251.TXT', 'windows-1251', 'cp1251', 'ibm-1251'),
        # latin - western europe
        ('manual/windows-1.0.txt', 'windows-1.0', 'windows-ansi-1.0', 'windows-1252-1.0'),
        ('manual/windows-2.0.txt', 'windows-2.0', 'windows-ansi-2.0', 'windows-1252-2.0'),
        ('manual/windows-3.1.txt', 'windows-3.1', 'windows-ansi-3.1', 'windows-1252-3.1'),
        ('microsoft/WINDOWS/CP1252.TXT', 'windows-1252', 'windows-ansi', 'ansi', 'ansinew', 'cp1252', 'ibm-1252'),
        # greek
        ('microsoft/WINDOWS/CP1253.TXT', 'windows-1253', 'greek-ansi', 'cp1253', 'ibm-1253'),
        # latin - turkish
        ('microsoft/WINDOWS/CP1254.TXT', 'windows-1254', 'cp1254', 'ibm-1254'),
        # hebrew
        ('microsoft/WINDOWS/CP1255.TXT', 'windows-1255', 'cp1255', 'ibm-1255'),
        # arabic
        ('microsoft/WINDOWS/CP1256.TXT', 'windows-1256', 'cp1256', 'ibm-1256'),
        # latin - baltic
        ('microsoft/WINDOWS/CP1257.TXT', 'windows-1257', 'windows-baltic', 'cp1257', 'ibm-1257', 'lst-1590-3'),
        # latin - vietnamese
        ('microsoft/WINDOWS/CP1258.TXT', 'windows-1258', 'cp1258', 'ibm-1258'),

        # IBM/OEM/MS-DOS codepages
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/PC
        ('microsoft/PC/CP437.TXT', 'cp437', 'oem-437', 'ibm-437', 'oem-us', 'pc-8', 'dos-latin-us'),
        ('microsoft/PC/CP737.TXT', 'cp737', 'oem-737', 'ibm-737', 'dos-greek'),
        ('microsoft/PC/CP775.TXT', 'cp775', 'oem-775', 'ibm-775', 'dos-baltic-rim', 'lst-1590-1'),
        ('microsoft/PC/CP850.TXT', 'cp850', 'oem-850', 'ibm-850', 'dos-latin-1'),
        ('microsoft/PC/CP852.TXT', 'cp852', 'oem-852', 'ibm-852', 'dos-latin-2'),
        ('microsoft/PC/CP855.TXT', 'cp855', 'oem-855', 'ibm-855', 'dos-cyrillic'),
        ('microsoft/PC/CP857.TXT', 'cp857', 'oem-857', 'ibm-857', 'dos-turkish'),
        ('microsoft/PC/CP860.TXT', 'cp860', 'oem-860', 'ibm-860', 'dos-portuguese'),
        ('microsoft/PC/CP861.TXT', 'cp861', 'oem-861', 'ibm-861', 'cp-is', 'dos-icelandic'),
        ('microsoft/PC/CP862.TXT', 'cp862', 'oem-862', 'ibm-862', 'dos-hebrew'),
        ('microsoft/PC/CP863.TXT', 'cp863', 'oem-863', 'ibm-863', 'dos-french-canada'),
        ('microsoft/PC/CP864.TXT', 'cp864', 'oem-864', 'ibm-864'), # dos-arabic
        ('microsoft/PC/CP865.TXT', 'cp865', 'oem-865', 'ibm-865', 'dos-nordic'),
        ('microsoft/PC/CP866.TXT', 'cp866', 'oem-866', 'ibm-866', 'dos-cyrillic-russian'),
        ('microsoft/PC/CP869.TXT', 'cp869', 'oem-869', 'ibm-869', 'dos-greek2'),
        ('microsoft/PC/CP874.TXT', 'ibm-874', 'ibm-9066'), # dos-thai

        # EBCDIC
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/EBCDIC
        ('microsoft/EBCDIC/CP037.TXT', 'cp037', 'ibm037', 'ebcdic-cp-us', 'ebcdic-cp-ca', 'ebcdic-cp-wt', 'ebcdic-cp-nl'),
        ('microsoft/EBCDIC/CP500.TXT', 'cp500', 'ibm500', 'ebcdic-international'),
        ('microsoft/EBCDIC/CP875.TXT', 'cp875', 'ibm875'),
        ('microsoft/EBCDIC/CP1026.TXT', 'cp1026', 'ibm1026'),

        # Apple codepages matching a script code
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/
        #
        # this will have the pre-euro version of the mac-roman set (aka microsoft's cp 10000)
        # microsoft's table substitutes the capital omega with the (equivalent) Ohm sign
        ('apple/ROMAN.TXT', 'mac-roman', 'mac', 'macintosh', 'ibm-1275', 'windows-10000'),
        #'apple/ROMAN.TXT', 'mac-roman-8.5', 'mac-8.5', 'macintosh-8.5', 'mac-roman-euro', 'mac-euro', 'macintosh-euro'),
        ('apple/JAPANESE.TXT', 'mac-japanese',),
        ('apple/CHINTRAD.TXT', 'mac-traditional-chinese', 'mac-trad-chinese', 'mac-chinese-trad'),
        ('apple/KOREAN.TXT', 'mac-korean',),
        ('apple/ARABIC.TXT', 'mac-arabic',),
        ('apple/HEBREW.TXT', 'mac-hebrew',),
        ('apple/GREEK.TXT', 'mac-greek',),
        # note: A2, B6, FF changed after mac-os 9.0
        # see https://en.wikipedia.org/wiki/Mac_OS_Cyrillic_encoding
        ('apple/CYRILLIC.TXT', 'mac-cyrillic',),
        ('apple/DEVANAGA.TXT', 'mac-devanagari',),
        ('apple/GURMUKHI.TXT', 'mac-gurmukhi',),
        ('apple/GUJARATI.TXT', 'mac-gujarati',),
        ('apple/THAI.TXT', 'mac-thai',) ,
        ('apple/CHINSIMP.TXT', 'mac-simplified-chinese', 'mac-simp-chinese', 'mac-chinese-simp'),
        # "non-cyrillic slavic", mac-centeuro
        # cf. 'microsoft/MAC/LATIN2.TXT'
        ('apple/CENTEURO.TXT', 'mac-centraleurope', 'mac-ce', 'mac-latin2', 'mac-centeuro', 'mac-east-eur-roman'),
        # Armenian and Georgian taken from Evertype:
        # https://www.evertype.com/standards/mappings/
        ('evertype/GEORGIAN.TXT', 'mac-georgian',),
        ('evertype/ARMENIAN.TXT', 'mac-armenian',),
        # Apple codepages not matching a script code
        ('apple/CELTIC.TXT', 'mac-celtic',),
        ('apple/CROATIAN.TXT', 'mac-croatian',),
        ('apple/DINGBATS.TXT', 'mac-dingbats',),
        ('apple/FARSI.TXT', 'mac-farsi',),
        ('apple/GAELIC.TXT', 'mac-gaelic',),
        ('apple/ICELAND.TXT', 'mac-icelandic',),
        ('apple/INUIT.TXT', 'mac-inuit',),
        ('apple/SYMBOL.TXT', 'mac-symbol', 'windows-symbol', 'microsoft-symbol'),
        ('apple/TURKISH.TXT', 'mac-turkish',),
        ('apple/UKRAINE.TXT', 'mac-ukrainian',),
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
        ('misc/KOI8-R.TXT', 'koi8-r', 'cp878'),
        ('misc/KOI8-U.TXT', 'koi8-u',),
        # hebrew
        ('misc/CP424.TXT', 'cp424', 'ebcdic-hebrew'),
        ('misc/CP856.TXT', 'cp856', 'oem-856', 'ibm-856'),
        # arabic - urdu
        ('misc/CP1006.TXT', 'cp1006', 'ibm-1006'),
        # APL
        ('misc/APL-ISO-IR-68.TXT', 'iso-ir-68',) ,
        # korean
        ('misc/KPS9566.TXT', 'kps-9566', 'iso-ir-202'),
        # cyrillic - kazakh
        ('misc/KZ1048.TXT', 'kz-1048', 'strk1048-2002', 'rk-1048'),

        # not loaded from misc/:
        # SGML.TXT
        # US-ASCII-QUOTES.TXT
        # 'misc/ATARIST.TXT', 'atari-st',),
        ('misc/NEXTSTEP.TXT', 'next', 'nextstep', 'next-multinational') ,
        ('misc/GSM0338.TXT', 'gsm-03.38', 'gsm'),

        # Roman Czyborra's codepage tables
        # cyrillic pages
        ('czyborra/koi-0.txt', 'koi0', 'gost-13052'),
        ('czyborra/koi-7.txt', 'koi7', 'gost-19768-74-7'),
        # koi-8 should be overlaid with ascii
        ('czyborra/koi8-a.txt', 'koi8-a', 'koi8', 'gost-19768-74-8'),
        ('czyborra/koi8-b.txt', 'koi8-b',),
        ('czyborra/koi8-f.txt', 'koi8-f', 'koi8-unified', 'koi8-uni'),
        ('czyborra/koi8-e.txt', 'koi8-e', 'iso-ir-111', 'ecma-cyrillic'),
        ('czyborra/gost19768-87.txt', 'gost-19768-87',) ,
        # use unicode.org misc/ mappings for KOI8-U and KOI8-U
        # 'koi8-r': 'czyborra/koi-8-e.txt',
        # 'koi8-u': 'czyborra/koi-8-e.txt',
        # use unicode.org microsoft/ mappings for cp866
        # 'cp866': 'czyborra/cp866.txt',
        ('czyborra/bulgarian-mik.txt', 'mik', 'bulgarian-mik', 'bulgaria-pc'),
        # latin pages
        ('czyborra/hp-roman8.txt', 'hp-roman8', 'ibm-1051'),
        ('czyborra/vn5712-1.txt', 'tcvn5712-1', 'vscii-1'),
        ('czyborra/vn5712-2.txt', 'tcvn5712-2', 'vscii-2'),

        # mleisher's csets
        ('mleisher/ALTVAR.TXT' , 'alternativnyj-variant', 'alternativnyj', 'av'),
        ('mleisher/ARMSCII-7.TXT' , 'armscii-7',),
        ('mleisher/ARMSCII-8.TXT' , 'armscii-8',),
        ('mleisher/ARMSCII-8A.TXT' , 'armscii-8a',),
        ('mleisher/DECMCS.TXT' , 'dec-mcs', 'dmcs', 'mcs', 'ibm-1100', 'cp1100'),
        ('mleisher/GEO-ITA.TXT' , 'georgian-academy', 'georgian-ita'),
        ('mleisher/GEO-PS.TXT' , 'georgian-parliament', 'georgian-ps'),
        ('mleisher/IRANSYSTEM.TXT' , 'iran-system', 'iransystem'),
        ('mleisher/KOI8RU.TXT' , 'koi8-ru',),
        ('mleisher/OSNOVAR.TXT' , 'osnovnoj-variant', 'osnovnoj', 'ov'),
        ('mleisher/RISCOS.TXT' , 'risc-os', 'acorn-risc-os'),
        # tis620-0 is an alias used in xorg
        ('mleisher/TIS620.TXT' , 'tis-620', 'tis620-0', 'iso-ir-166'),

        # IANA registrations
        ('iana/Amiga-1251', 'amiga-1251', 'ami1251',),

        # X11 xfonts
        ('xfonts/viscii1.1-1.enc', 'viscii', 'viscii1.1-1'),

        # manually adapted
        ('manual/ms-linedraw.txt', 'windows-linedraw', 'microsoft-linedraw', 'ms-linedraw'),
        ('manual/hp48.txt', 'hp-48', 'hp48', 'hp-rpl'),
    )),

    ('adobe', {}, (
        # Adobe encodings
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/ADOBE/
        ('adobe/stdenc.txt', 'adobe-standard',),
        ('adobe/symbol.txt', 'adobe-symbol',),
        ('adobe/zdingbat.txt', 'adobe-dingbats',),

        # IBM PC memory-mapped video graphics, overlaying the control character range
        # to be used in combination with other code pages e.g. cp437
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MISC/
        ('misc/IBMGRAPH.TXT', 'ibm-graphics',),
    )),

    ('ucm', {}, (
        # charmaps from Keld Simonsen (dkuug)
        ('dkuug/iso646-us', 'ascii', 'iso646-us', 'ascii-0', 'us-ascii', 'iso-ir-6', 'ansi-x3.4-1968'),
        ('dkuug/iso646-ca', 'iso646-ca', 'iso-ir-121', 'csa7-1'),
        ('dkuug/iso646-ca2', 'iso646-ca2', 'iso-ir-122', 'csa7-2'),
        ('dkuug/iso646-cn', 'iso646-cn', 'iso-ir-57', 'gbt-1988-80'),
        ('dkuug/iso646-de', 'iso646-de', 'iso-ir-21', 'din-66003'),
        ('dkuug/iso646-dk', 'iso646-dk', 'ds-2089'),
        ('dkuug/iso646-es', 'iso646-es', 'iso-ir-17'),
        ('dkuug/iso646-es2', 'iso646-es2', 'iso-ir-85'),
        ('dkuug/iso646-fr', 'iso646-fr', 'iso-ir-69'),
        ('dkuug/iso646-gb', 'iso646-gb', 'iso-ir-4', 'bs-4730'),
        ('dkuug/iso646-hu', 'iso646-hu', 'iso-ir-86', 'msz7795-3'),
        ('dkuug/iso646-it', 'iso646-it', 'iso-ir-15', 'uni-0204-70'),
        ('dkuug/iso646-jp', 'iso646-jp', 'iso-ir-14', 'jiscii', 'jis-roman', 'ibm-895'),
        ('dkuug/iso646-kr', 'iso646-kr',),
        ('dkuug/iso646-yu', 'iso646-yu', 'iso-ir-141', 'yuscii-latin', 'croscii', 'sloscii', 'jus-i.b1.002'),
        # ibm-897 extends jis-x0201
        ('dkuug/jis_x0201', 'jis-x0201', 'jis-c-6220'),
        ('dkuug/x0201-7', 'x0201-7', 'iso-ir-13'),

        # charmaps from IBM/Unicode ICU project
        ('icu/ibm-1125_P100-1997.ucm', 'ruscii', 'ibm-1125', 'cp866u', 'cp866nav'),
        ('icu/ibm-720_P100-1997.ucm', 'cp720', 'ibm-720', 'transparent-asmo'),
        ('icu/ibm-858_P100-1997.ucm', 'cp858', 'ibm-858', 'cp850-euro'),
        ('icu/ibm-868_P100-1995.ucm', 'cp868', 'ibm-868', 'cp-ar', 'dos-urdu'),
        ('icu/ibm-851_P100-1995.ucm', 'cp851', 'ibm-851', 'oem-851'),
        ('icu/windows-936-2000.ucm', 'windows-936', 'ibm-1386', 'windows-gb2312', 'windows-gbk'),
        ('icu/ibm-1375_P100-2008.ucm', 'big5-hkscs', 'ibm-1375', 'big5hk'),
        ('icu/ibm-806_P100-1998.ucm', 'cp806', 'ibm-806', 'ibm-iscii-devanagari'),
    )),

    ('ucp', {}, (
        # manually constructed based on gif images
        # https://web.archive.org/web/20061017214053/http://www.cyrillic.com/ref/cyrillic/
        ('manual/russup3.ucp', 'dos-russian-support-3', 'rs3', 'russup3'),
        ('manual/russup4ac.ucp', 'dos-russian-support-4-academic', 'rs4ac', 'russup4ac'),
        ('manual/russup4na.ucp', 'dos-russian-support-4', 'rs4', 'russup4na'),

        # from wikipedia
        ('manual/zx-spectrum.ucp', 'zx-spectrum',),

        # from ibm cdra but overlaid with 437
        ('manual/cp934.ucp', 'cp934', 'ibm-934', 'dos-v-korean'),
        ('manual/cp938.ucp', 'cp938', 'ibm-938', 'dos-v-chinese-traditional'),
    )),

    ('html', {}, (
        ('wikipedia/mazovia.html', 'mazovia', 'cp667', 'cp790', 'cp991'),
        ('wikipedia/kamenicky.html', 'kamenický', 'kamenicky', 'nec-867', 'keybcs2', 'dos-895'),
        ('wikipedia/cwi2.html', 'cwi-2', 'cwi', 'cp-hu', 'hucwi', 'hu8cwi2'),
        ('wikipedia/pascii.html', 'pascii',),
        ('wikipedia/cp853.html', 'cp853', 'ibm-853'),
        ('wikipedia/brascii.html', 'brascii', 'abnt', 'star-3847'),
        ('wikipedia/abicomp.html', 'abicomp', 'star-3848', 'freedos-3848'),

        # DEC character sets
        ('wikipedia/dec-special.html', 'dec-special', 'ibm-1090'),
        ('wikipedia/dec-technical.html', 'dec-technical', 'dec-tcs', 'tcs'),

        # font-specific
        ('wikipedia/wingdings.html', 'wingdings', 'windows-wingdings', 'microsoft-wingdings'),

        # platform-specific charmaps
        ('wikipedia/amstrad-cpc.html', 'amstrad-cpc',),
        ('wikipedia/amstrad-cpm-plus.html', 'amstrad-cpm-plus', 'amstrad-pcw', 'zx-spectrum-plus3'),
        ('wikipedia/atari-st.html', 'atari-st',),
        ('wikipedia/gem.html', 'gem',),
        ('wikipedia/zx80.html', 'zx80',),
        ('wikipedia/zx81.html', 'zx81',),
        ('wikipedia/wiscii.html', 'wiscii', 'wang'),
        ('wikipedia/petscii.html', 'petscii-unshifted', 'petscii-0', 'petscii'),
    )),

    ('html', dict(range=range(0x80)), (
        ('wikipedia/atascii.html', 'atascii',),
    )),

    ('html', dict(column=1), (
        ('wikipedia/petscii.html', 'petscii-shifted', 'petscii-1'),
    )),
)

# charmaps to be overlaid with IBM graphics in range 0x00--0x1f and 0x7f
_ASCII_RANGE = tuple((_cp,) for _cp in range(0x80))
_IBM_GRAPH_RANGE = tuple((_cp,) for _cp in range(0x20)) + ((0x7f,),)
_MAC_GRAPH_RANGE = tuple((_cp,) for _cp in range(0x11, 0x15))
_MAC_EURO = ((0xDB,))
_OVERLAYS = (
    # these were partially defined, complete them by adding 7-bit ascii codepoints
    ('iso-8859/8859-1.TXT', _ASCII_RANGE, 'txt', {}, (
        'koi8-a', 'koi8-b', 'koi8-e', 'koi8-f', 'gost-19768-87', 'mik',
        # per NEXTSTEP.TXT, identical to ascii.
        # wikipedia suggests it's us-ascii-quotes
        'next',
        'rs3', 'rs4', 'rs4ac', 'mazovia', 'kamenicky', 'cwi-2', 'viscii',
        'cp853',
    )),
    # DOS/OEM codepages usually have the ibm-graphics range of icons mapped to C0 cntrols
    ('misc/IBMGRAPH.TXT', _IBM_GRAPH_RANGE, 'adobe', {}, (
        'cp437', 'cp720', 'cp737', 'cp775', 'cp806',
        'cp850', 'cp851', 'cp852', 'cp853', 'cp855', 'cp856', 'cp857', 'cp858',
        'cp860', 'cp861', 'cp862', 'cp863', 'cp865', 'cp866', 'cp868', 'cp869', # not cp864
        'cp874',
        'windows-950',
        'mik', 'koi8-r', 'koi8-u', 'koi8-ru', 'ruscii', 'rs3', 'rs4', 'rs4ac',
        'mazovia', 'kamenicky', 'cwi-2',
    )),
    # Mac OS system fonts
    ('manual/mac-system.ucp', _MAC_GRAPH_RANGE, 'ucp', {}, ('mac-roman', 'mac-roman-8.5')),
    ('manual/mac-roman-pre8.5.ucp', _MAC_EURO, 'ucp', {}, ('mac-roman',)),
    # there's a different ordering of the ibm graphics range specially for cp864
    ('misc/IBMGRAPH.TXT', _IBM_GRAPH_RANGE, 'txt', dict(
        codepoint_column=2, unicode_column=0
    ), ('cp864',)),
)


###################################################################################################
# character properties

def is_fullwidth(char):
    """Check if a character / grapheme sequence is fullwidth."""
    return any(
        unicodedata.east_asian_width(_c) in ('W', 'F')
        for _c in char
    )

def is_graphical(char):
    """Check if a char has a graphical representation."""
    return any(
        # str.isprintable includes everything but Other (C) and Separator (Z), plus SPACE
        # we keep everything but
        # Other/Control (Cc), Other/Surrogate (Cs), Separator/Line (Zl), Separator/Paragraph (Zp)
        # so we keep all spaces (Zs); PUA (Co); Other/Format (Cf) which has things like SOFT HYPHEN
        # also Not Assigned (Cn) - as unicodedata is not up to date
        # anything excluded will be dropped from our charmaps
        unicodedata.category(_c) not in ('Cc', 'Cs', 'Zl', 'Zp')
        for _c in char
    )

def is_printable(char):
    """Check if a char should be printed - nothing ambiguous or unrepresentable in there."""
    return (not char) or is_graphical(char) and all(
        # str.isprintable includes everything but Other (C) and Separator (Z), plus SPACE
        # we keep everything that is_graphical except PUA, Other/Format, Not Assigned
        # anything excluded will be shown as REPLACEMENT CHARACTER
        unicodedata.category(_c) not in ('Co', 'Cf', 'Cn')
        for _c in char
    )

def is_private_use(char):
    """Check if any char is in the private use area."""
    return any(
        unicodedata.category(_c) == 'Co'
        for _c in char
    )


###################################################################################################
# charmap registry

class NotFoundError(KeyError):
    """Encoding not found."""


class CharmapRegistry:
    """Register and retrieve charmaps."""

    # table of user-registered or -overlaid charmaps
    _registered = {}
    _overlays = {}

    # table of encoding aliases
    _aliases = {
        'ucs': 'unicode',
        'iso10646': 'unicode',
        'iso10646-1': 'unicode',
    }

    # replacement patterns for normalisation
    # longest first to avoid partial match
    _patterns = {
        'microsoftcp': 'windows',
        'microsoft': 'windows',
        'msdoscp': 'oem',
        'oemcp': 'oem',
        'msdos': 'oem',
        'ibmcp': 'ibm',
        'apple': 'mac',
        'macos': 'mac',
        'doscp': 'oem',
        'mscp': 'windows',
        'dos': 'oem',
        'pc': 'oem',
        'ms': 'windows',
        # mac-roman also known as x-mac-roman etc.
        'x': '',
    }

    @classmethod
    def register(cls, name, filename, format=None, **kwargs):
        """Register a file to be loaded for a given charmap."""
        normname = cls._normalise_for_match(name)
        if normname in cls._registered:
            logging.warning(
                f"Redefining character map '{name}'=='{cls._registered[normname]['name']}'."
            )
        if normname in cls._overlays:
            del cls._overlays[normname]
        cls._registered[normname] = dict(name=name, filename=filename, format=format, **kwargs)

    @classmethod
    def overlay(cls, name, filename, overlay_range, format=None, **kwargs):
        """Overlay a given charmap with an additional file."""
        normname = cls._normalise_for_match(name)
        ovr_dict = dict(
            name=name, filename=filename, format=format, codepoint_range=overlay_range,
            **kwargs
        )
        try:
            cls._overlays[normname].append(ovr_dict)
        except KeyError:
            cls._overlays[normname] = [(ovr_dict)]

    @classmethod
    def alias(cls, alias, name):
        """Define an alias for an encoding name."""
        name = cls._normalise_for_match(name)
        alias = cls._normalise_for_match(alias)
        if name == alias:
            # equal after normalisation
            return
        if alias in cls._registered:
            raise ValueError(
                f"Character set alias '{alias}' for '{name}' collides with registered name."
            )
        if alias in cls._aliases:
            logging.warning(
                'Redefining character set alias: now %s==%s (was %s).',
                alias, name, cls._aliases[alias]
            )
        cls._aliases[alias] = name

    @classmethod
    def is_unicode(cls, name):
        """Encoding name is equivalent to unicode."""
        return cls.match(name, 'unicode')

    @staticmethod
    def normalise(name):
        """Replace encoding name with normalised variant for display."""
        return name.lower().replace('_', '-').replace(' ', '-')

    @classmethod
    def match(cls, name1, name2):
        """Check if two names match."""
        return cls._normalise_for_match(name1) == cls._normalise_for_match(name2)

    @classmethod
    def _normalise_for_match(cls, name):
        """Further normalise names to base form and apply aliases for matching."""
        # all lowercase
        name = name.lower()
        # remove spaces, dashes and dots
        for char in '._- ':
            name = name.replace(char, '')
        try:
            # anything that's in the alias table
            return cls._aliases[name]
        except KeyError:
            pass
        # try replacements
        for start, replacement in cls._patterns.items():
            if name.startswith(start):
                name = replacement + name[len(start):]
                break
        # found in table after replacement?
        return cls._aliases.get(name, name)

    @staticmethod
    def load(*args, **kwargs):
        """Create new charmap from file."""
        return Charmap.load(*args, **kwargs)

    @staticmethod
    def create(*args, **kwargs):
        """Create new charmap from mapping."""
        return Charmap(*args, **kwargs)

    def __iter__(self):
        """Iterate over names of registered charmaps."""
        return iter(_v['name'] for _v in self._registered.values())

    def __getitem__(self, name):
        """Get charmap from registry by name; raise NotFoundError if not found."""
        if self.is_unicode(name):
            return Unicode()
        normname = self._normalise_for_match(name)
        try:
            charmap_dict = self._registered[normname]
        except KeyError as exc:
            raise NotFoundError(f"No registered character map matches '{name}'.") from exc
        charmap = self.load(**charmap_dict)
        for ovr_dict in self._overlays.get(normname, ()):
            ovr_rng = ovr_dict.pop('codepoint_range')
            overlay = self.load(**ovr_dict)
            charmap = charmap.overlay(overlay, ovr_rng)
        return charmap

    def fit(self, charmap):
        """Return best-fit registered charmap."""
        min_dist = len(charmap)
        fit = Charmap()
        for registered in self:
            registered_map = self[registered]
            dist = charmap.distance(registered_map)
            if dist == 0:
                return registered_map
            elif dist < min_dist:
                min_dist = dist
                fit = registered_map
        return fit

    def __repr__(self):
        """String representation."""
        return (
            "CharmapRegistry('"
            + "', '".join(self)
            + "')"
        )


###################################################################################################
# encoder/charmap classes

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
        """Chart of page in charmap."""
        bg = '\u2591'
        cps = range(256)
        cps = (((page, _c) if page else (_c,)) for _c in cps)
        chars = (self.char(_cp) for _cp in cps)
        chars = ((_c if is_printable(_c) else '\ufffd') for _c in chars)
        chars = ((_c if is_fullwidth(_c) else ((_c + ' ') if _c else bg*2)) for _c in chars)
        # deal with Nonspacing Marks while keeping table format
        chars = ((' ' +_c if unicodedata.category(_c[:1]) == 'Mn' else _c) for _c in chars)
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
        return f"{type(self).__name__}(name='{self.name}')"


class Charmap(Encoder):
    """Convert between unicode and ordinals using stored mapping."""

    # charmap file format parameters
    _formats = {}

    def __init__(self, mapping=None, *, name=''):
        """Create charmap from a dictionary codepoint -> char."""
        if not mapping:
            mapping = {}
            name = ''
        super().__init__(CharmapRegistry.normalise(name))
        # copy dict - ignore mappings to non-graphical characters (controls etc.)
        self._ord2chr = {_k: _v for _k, _v in mapping.items() if is_graphical(_v)}
        self._chr2ord = {_v: _k for _k, _v in self._ord2chr.items()}

    @classmethod
    def register_loader(cls, format, **default_kwargs):
        """Decorator to register charmap reader."""
        def decorator(reader):
            cls._formats[format] = (reader, default_kwargs)
            return reader
        return decorator

    @classmethod
    def load(cls, filename, *, format=None, name='', **kwargs):
        """Create new charmap from file."""
        try:
            data = pkgutil.get_data(__name__, filename)
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load charmap file `{filename}`: {exc}')
        if not data:
            raise NotFoundError(f'No data in charmap file `{filename}`.')
        format = format or Path(filename).suffix[1:].lower()
        try:
            reader, format_kwargs = cls._formats[format]
        except KeyError as exc:
            raise NotFoundError(f'Undefined charmap file format {format}.') from exc
        mapping = reader(data, **{**format_kwargs, **kwargs})
        if not name:
            name = Path(filename).stem
        return cls(mapping, name=name)

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

    def __len__(self):
        """Number of defined codepoints."""
        return len(self._ord2chr)

    def __eq__(self, other):
        """Compare to other Charmap."""
        return isinstance(other, Charmap) and (self._ord2chr == other._ord2chr)

    def __sub__(self, other):
        """Return encoding with only characters that differ from right-hand side."""
        return Charmap(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if other.char(_k) != _v},
            name=f'[{self.name}]-[{other.name}]'
        )

    def __add__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        mapping = {**self.mapping}
        mapping.update(other.mapping)
        return Charmap(mapping=mapping, name=f'{self.name}')

    def distance(self, other):
        """Return number of different code points."""
        other_only = set(other._ord2chr) - set(self._ord2chr)
        self_only = set(self._ord2chr) - set(other._ord2chr)
        different = set(
            _k for _k, _v in self._ord2chr.items()
            if _k in other._ord2chr and other.char(_k) != _v
        )
        return len(different) + len(other_only) + len(self_only)

    def take(self, codepoint_range):
        """Return encoding only for given range of codepoints."""
        return Charmap(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if _k in codepoint_range},
            name=f'subset[{self.name}]'
        )

    def overlay(self, other, codepoint_range):
        """Return encoding overlaid with all characters in the overlay range taken from rhs."""
        return self + other.take(codepoint_range)

    def __repr__(self):
        """Representation."""
        if self._ord2chr:
            mapping = f'<{len(self._ord2chr)} code points>'
            table = f'\n{self.table()}\n'
            return (
                f"{type(self).__name__}(name='{self.name}', mapping={mapping}){table}"
            )
        return (
            f"{type(self).__name__}()"
        )


class Unicode(Encoder):
    """Convert between unicode and ordinals."""

    def __init__(self):
        """Unicode converter."""
        super().__init__('unicode')

    @staticmethod
    def char(codepoint):
        """Convert codepoint to character."""
        return ''.join(chr(_i) for _i in codepoint if is_graphical(chr(_i)))

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
# charmap file readers

@Charmap.register_loader('txt')
@Charmap.register_loader('enc')
@Charmap.register_loader('ucp', separator=':', joiner=',')
@Charmap.register_loader('adobe', separator='\t', joiner=None, codepoint_column=1, unicode_column=0)
def _from_text_columns(
        data, *, comment='#', separator=None, joiner='+', codepoint_column=0, unicode_column=1,
        codepoint_base=16, unicode_base=16, inline_comments=True
    ):
    """Extract character mapping from text columns in file data (as bytes)."""
    mapping = {}
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('START') or line.startswith('END'):
            # xfonts .enc files - STARTENCODING, STARTMAPPING etc.
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
                # allow sequence of codepoints
                # multibyte code points can also be given as single large number
                cp_point = b''.join(
                    int_to_bytes(int(_substr, codepoint_base))
                    for _substr in cp_str.split(joiner)
                )
                cp_point = tuple(cp_point)
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
                logging.warning('Could not parse line in text charmap file: %s [%s]', e, repr(line))
    return mapping


@Charmap.register_loader('ucm')
def _from_ucm_charmap(data):
    """Extract character mapping from icu ucm / linux charmap file data (as bytes)."""
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
        cp_bytes, uni_str = '', ''
        for item in splitline:
            if item.startswith('<U'):
                # e.g. <U0000> or <U2913C>
                uni_str = item[2:-1]
            elif item.startswith(escape + 'x'):
                cp_str = item.replace(escape + 'x', '')
                cp_bytes = binascii.unhexlify(cp_str)
            elif item.startswith(precision):
                # precision indicator
                # |0 - A “normal”, roundtrip mapping from a Unicode code point and back.
                # |1 - A “fallback” mapping only from Unicode to the codepage, but not back.
                # |2 - A subchar1 mapping. The code point is unmappable, and if a substitution is
                #      performed, then the subchar1 should be used rather than the subchar.
                #      Otherwise, such mappings are ignored.
                # |3 - A “reverse fallback” mapping only from the codepage to Unicode, but not back
                #      to the codepage.
                # |4 - A “good one-way” mapping only from Unicode to the codepage, but not back.
                if item[1:].strip() != '0':
                    # only accept 'normal' mappings
                    # should we also allow "reverse fallback" ?
                    break
        else:
            if not uni_str or not cp_str:
                logging.warning('Could not parse line in ucm charmap file: %s.', repr(line))
                continue
            cp_point = tuple(cp_bytes)
            if cp_point in mapping:
                logging.debug('Ignoring redefinition of code point %s', cp_point)
            else:
                mapping[cp_point] = chr(int(uni_str, 16))
    return mapping


@Charmap.register_loader('html')
def _from_wikipedia(data, table=0, column=0, range=None):
    """
    Scrape charmap from table in Wikipedia.
    Reads matrix tables with class="chset".
    table: target table; 0 for 1st chset table, etc.
    column: target column if multiple unicode points provided per cell.
    range: range to read, read all if range is empty
    """

    class _WikiParser(HTMLParser):
        """HTMLParser object to read Wikipedia tables."""

        def __init__(self):
            """Set up Wikipedia parser."""
            super().__init__()
            # output dict
            self.mapping = {}
            # state variables
            # parsing chset table
            self.table = False
            self.count = 0
            # data element
            self.td = False
            # the unicode point is surrounded by <small> tags
            self.small = False
            # parse row header
            self.th = False
            # current codepoint
            self.current = 0

        def handle_starttag(self, tag, attrs):
            """Change state upon encountering start tag."""
            attrs = dict(attrs)
            if (
                    tag == 'table'
                    and 'class' in attrs
                    and 'chset' in attrs['class']
                    and self.count == table
                ):
                self.table = True
                self.th = False
                self.td = False
                self.small = False
            elif self.table:
                if tag == 'td':
                    self.td = True
                    self.small = False
                elif tag == 'small':
                    self.small = True
                elif tag == 'th':
                    self.th = True

        def handle_endtag(self, tag):
            """Change state upon encountering end tag."""
            if tag == 'table':
                if self.table:
                    self.count += 1
                self.table = False
                self.th = False
                self.td = False
                self.small = False
            elif tag == 'td':
                self.td = False
                self.current += 1
            elif tag == 'style':
                self.small = False
            elif tag == 'th':
                self.th = False

        def handle_data(self, data):
            """Parse cell data, depending on state."""
            # row header provides first code point of the row
            if self.th and len(data) == 2 and data[-1] == '_':
                self.current = int(data[0],16) * 16
            # unicode point in <small> tag in table cell
            if self.td and self.small:
                cols = data.split()
                if len(cols) > column:
                    data = cols[column]
                if len(data) >= 4:
                    # unicode point
                    if data.lower().startswith('u+'):
                        data = data[2:]
                    if not range or self.current in range:
                        try:
                            char = chr(int(data, 16))
                        except ValueError:
                            # not a unicode point
                            pass
                        else:
                            self.mapping[(self.current,)] = char

    parser = _WikiParser()
    parser.feed(data.decode('utf-8-sig'))
    return parser.mapping


###################################################################################################

charmaps = CharmapRegistry()

# charmap files
for _format, _kwargs, _records in _ENCODING_FILES:
    for _file, _name, *_aliases in _records:
        charmaps.register(_name, f'charmaps/{_file}', _format, **_kwargs)
        for _alias in _aliases:
            charmaps.alias(_alias, _name)

# overlays
for _overlay, _range, _format, _kwargs, _names in _OVERLAYS:
    for _name in _names:
        charmaps.overlay(_name, f'charmaps/{_overlay}', _range, _format, **_kwargs)
