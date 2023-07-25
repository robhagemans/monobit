"""
monobit.encoding.charmaps.definitions - character map definitions

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from importlib.resources import files

from . import loaders


def register_charmaps(charmaps):
    """Register charmap files"""
    for _format, _kwargs, _records in _ENCODING_FILES:
        for _file, _name, *_aliases in _records:
            charmaps.register(_name, _file, _format, **_kwargs)
            for _alias in _aliases:
                charmaps.alias(_alias, _name)
    # overlays
    for _overlay, _range, _format, _kwargs, _names in _OVERLAYS:
        for _name in _names:
            charmaps.overlay(_name, _overlay, _range, _format, **_kwargs)
    # FreeDOS charmaps
    for _file in files('monobit.encoding.tables.freedos').iterdir():
        if Path(_file.name).suffix != '.md':
            charmaps.register(f'freedos-{Path(_file.name).stem}', 'freedos/{_file.name}')



_ENCODING_FILES = (

    ('txt', {}, (
        # iso standards
        # https://www.unicode.org/Public/MAPPINGS/ISO8859
        ('iso-8859/8859-1.TXT', 'latin-1', 'iso8859-1', 'iso-ir-100', 'ibm-819', 'windows-28591'),
        ('iso-8859/8859-2.TXT', 'latin-2', 'iso8859-2', 'iso-ir-101', 'ibm-1111', 'windows-28592'),
        ('iso-8859/8859-3.TXT', 'latin-3', 'iso8859-3', 'iso-ir-109', 'ibm-913', 'windows-28593'),
        ('iso-8859/8859-4.TXT', 'latin-4', 'iso8859-4', 'iso-ir-110', 'ibm-914', 'windows-28594'),
        ('iso-8859/8859-5.TXT', 'iso8859-5', 'cyrillic', 'latin-cyrillic', 'iso-ir-144', 'ecma-113', 'windows-28595'),
        ('iso-8859/8859-6.TXT', 'iso8859-6', 'arabic', 'latin-arabic', 'asmo-708', 'iso-ir-127', 'ecma-114', 'windows-28596', 'windows-38596'),
        ('iso-8859/8859-7.TXT', 'iso8859-7', 'greek', 'latin-greek', 'greek8', 'iso-ir-126', 'ibm-813', 'elot-928', 'ecma-118', 'windows-28597'),
        ('iso-8859/8859-8.TXT', 'iso8859-8', 'hebrew', 'latin-hebrew', 'iso-ir-138', 'ibm-916', 'ecma-121', 'windows-28598', 'windows-38598'),
        ('iso-8859/8859-9.TXT', 'iso8859-9', 'latin-5', 'turkish', 'iso-ir-148', 'ibm-920', 'ecma-128', 'windows-28599'),
        ('iso-8859/8859-10.TXT', 'iso8859-10', 'latin-6', 'ibm-919', 'iso-ir-157', 'ecma-144', 'windows-28600'),
        # differs from tis-620 only in a code point mapping NBSP
        ('iso-8859/8859-11.TXT', 'iso8859-11', 'latin-thai', 'windows-28601'),
        ('iso-8859/8859-13.TXT', 'iso8859-13', 'latin-7', 'baltic-rim', 'ibm-921', 'iso-ir-179', 'windows-28603'),
        ('iso-8859/8859-14.TXT', 'iso8859-14', 'latin-8', 'celtic', 'iso-celtic', 'iso-ir-199', 'windows-28604'),
        ('iso-8859/8859-15.TXT', 'iso8859-15', 'latin-9', 'latin-0', 'windows-28605'),
        ('iso-8859/8859-16.TXT', 'iso8859-16', 'latin-10', 'sr-14111', 'iso-ir-226', 'windows-28606'),

        # Windows codepages
        # https://www.unicode.org/Public/MAPPINGS/VENDORS/MICSFT/WINDOWS
        # thai
        # tis620-2 is the name used in xorg
        # the xorg encoding also adds some PUA mappings on undefined code points
        ('microsoft/WINDOWS/CP874.TXT', 'windows-874', 'ibm-1162', 'tis620-2'),
        # japanese shift-jis
        ('microsoft/WINDOWS/CP932.TXT', 'windows-932', 'windows-31j', 'ms-kanji', 'windows-shift-jis'),
        # ibm variant adds graphical characters
        ('microsoft/WINDOWS/CP932.TXT', 'ibm-943', 'cp943c'),
        # simplified chinese gbk
        # use more extensive version from icu by default
        #'microsoft/WINDOWS/CP936.TXT', 'windows-936', 'ibm-1386'),
        # korean extended wansung / unified hangul code
        # this is an extension of euc-kr, wansung
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
        ('microsoft/PC/CP869.TXT', 'cp869', 'oem-869', 'ibm-869', 'dos-greek2', 'pcl-greek8'),
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
        # microsoft's cp10000 table has pre-euro and substitutes the capital omega with the (equivalent) Ohm sign
        # 1985 macroman was undefined in the range 0xD9-0xFF inclusive:
        # https://vintageapple.org/inside_o/pdf/Inside_Macintosh_Volume_I_1985.pdf#page=259
        # this also doesn't show the system icons 0x11-0x14
        # but they are often left out of such tables as they shadow controls
        ('apple/ROMAN.TXT', 'mac-roman', 'mac', 'macintosh', 'ibm-1275', 'windows-10000'),
        #'apple/ROMAN.TXT', 'mac-roman-8.5', 'mac-8.5', 'macintosh-8.5', 'mac-roman-euro', 'mac-euro', 'macintosh-euro'),
        ('apple/JAPANESE.TXT', 'mac-japanese', 'windows-10001'),
        ('apple/CHINTRAD.TXT', 'mac-traditional-chinese', 'mac-trad-chinese', 'mac-chinese-trad', 'windows-10002'),
        ('apple/KOREAN.TXT', 'mac-korean', 'windows-10003'),
        ('apple/ARABIC.TXT', 'mac-arabic', 'windows-10004'),
        ('apple/HEBREW.TXT', 'mac-hebrew', 'windows-10005'),
        ('apple/GREEK.TXT', 'mac-greek', 'windows-10006'),
        # note: A2, B6, FF changed after mac-os 9.0
        # see https://en.wikipedia.org/wiki/Mac_OS_Cyrillic_encoding
        ('apple/CYRILLIC.TXT', 'mac-cyrillic', 'windows-10007'),
        ('apple/DEVANAGA.TXT', 'mac-devanagari',),
        ('apple/GURMUKHI.TXT', 'mac-gurmukhi',),
        ('apple/GUJARATI.TXT', 'mac-gujarati',),
        ('apple/THAI.TXT', 'mac-thai', 'windows-10021') ,
        ('apple/CHINSIMP.TXT', 'mac-simplified-chinese', 'mac-simp-chinese', 'mac-chinese-simp', 'windows-10008'),
        # "non-cyrillic slavic", mac-centeuro
        # cf. 'microsoft/MAC/LATIN2.TXT'
        ('apple/CENTEURO.TXT', 'mac-centraleurope', 'mac-ce', 'mac-latin2', 'mac-centeuro', 'mac-east-eur-roman', 'mac-roman2', 'windows-10029'),
        # Armenian and Georgian taken from Evertype:
        # https://www.evertype.com/standards/mappings/
        ('evertype/GEORGIAN.TXT', 'mac-georgian',),
        ('evertype/ARMENIAN.TXT', 'mac-armenian',),
        # Apple codepages not matching a script code
        ('apple/CELTIC.TXT', 'mac-celtic',),
        ('apple/CROATIAN.TXT', 'mac-croatian', 'windows-10082'),
        ('apple/DINGBATS.TXT', 'mac-dingbats',),
        ('apple/FARSI.TXT', 'mac-farsi',),
        ('apple/GAELIC.TXT', 'mac-gaelic',),
        ('apple/ICELAND.TXT', 'mac-icelandic', 'windows-10079'),
        ('apple/INUIT.TXT', 'mac-inuit',),
        ('apple/SYMBOL.TXT', 'mac-symbol', 'windows-symbol', 'microsoft-symbol'),
        ('apple/ROMANIAN.TXT', 'mac-romanian', 'windows-10010'),
        ('apple/TURKISH.TXT', 'mac-turkish', 'windows-10081'),
        # UKRAINE.TXT has no mapping
        ('apple/CYRILLIC.TXT', 'mac-ukrainian', 'windows-10017'),
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
        ('czyborra/koi8-f.txt', 'koi8-unified', 'koi8-f', 'koi8-uni'),
        ('czyborra/koi8-e.txt', 'koi8-e', 'iso-ir-111', 'ecma-cyrillic'),
        ('czyborra/gost19768-87.txt', 'gost-19768-87',) ,
        # use unicode.org misc/ mappings for KOI8-U and KOI8-U
        # 'koi8-r': 'czyborra/koi-8-e.txt',
        # 'koi8-u': 'czyborra/koi-8-e.txt',
        # use unicode.org microsoft/ mappings for cp866
        # 'cp866': 'czyborra/cp866.txt',
        ('czyborra/bulgarian-mik.txt', 'mik', 'bulgarian-mik', 'bulgaria-pc'),
        # latin pages
        ('czyborra/hp-roman8.txt', 'hp-roman8', 'ibm-1051', 'cp1051', 'roman8'),

        # Jean-Cristophe André at bugs.python.org
        # tcvn3 <= tcvn2 <= tcvn1
        ('python/TCVN5712-1.TXT', 'tcvn5712-1', 'vscii-1', 'vscii', 'tcvn-1', 'iso-ir-180'),
        ('python/TCVN5712-2.TXT', 'tcvn5712-2', 'vscii-2', 'tcvn-2'),
        ('python/TCVN5712-3.TXT', 'tcvn5712-3', 'vscii-3', 'tcvn-3'),

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
        # tis620-0 is an alias used in xorg
        ('mleisher/TIS620.TXT' , 'tis-620', 'tis620-0', 'iso-ir-166'),

        # IANA registrations
        ('iana/Amiga-1251', 'amiga-1251', 'ami1251',),
        ('iana/PTCP154', 'paratype-154', 'ptcp-154', 'pt154', 'cyrillic-asian'),

        # X11 xfonts
        # xfonts's viscii is not correct
        #('xfonts/viscii1.1-1.enc', 'viscii', 'viscii1.1-1'),
        # variant of iso8859-7
        ('xfonts/suneu-greek.enc', 'suneu-greek',),
        # multilingual emacs encodings
        ('xfonts/mulelao-1.enc', 'mule-lao', 'mulelao-1'),
        ('xfonts/mulearabic-0.enc', 'arabic-digit', 'mulearabic-0'),
        ('xfonts/mulearabic-1.enc', 'arabic-1-column', 'mulearabic-1'),
        ('xfonts/mulearabic-2.enc', 'arabic-2-column', 'mulearabic-2'),

        # GNU emacs MULE
        # these are shifted to the lower 7 bits, except mule-lao above
        ('emacs/MULE-ethiopic.map', 'mule-ethiopic',),
        ('emacs/MULE-ipa.map', 'mule-ipa',),
        ('emacs/MULE-sisheng.map', 'mule-sisheng', 'sisheng',),
        ('emacs/MULE-is13194.map', 'mule-is13194', 'mule-iscii'),
        ('emacs/MULE-tibetan.map', 'mule-tibetan',),
        ('emacs/MULE-lviscii.map', 'mule-lviscii', 'viscii-lower'),
        ('emacs/MULE-uviscii.map', 'mule-uviscii', 'viscii-upper'),

        # Rebecca Bettencourt / KreativeKorp / Unicode Legacy Computing
        # attachments to Unicode proposal L2/19-025
        ('kreativekorp/ADAMOS7.TXT', 'coleco-adam-os7', 'adam-os7'),
        ('kreativekorp/ADAMSWTR.TXT', 'coleco-adam-smartwriter', 'adam-smartwriter'),
        ('kreativekorp/AMSCPC.TXT', 'amstrad-cpc',),
        ('kreativekorp/AMSCPM.TXT', 'amstrad-cpm-plus', 'amstrad-pcw', 'zx-spectrum-plus3', 'zx-spectrum-3plus'),
        ('kreativekorp/APL2PRIM.TXT', 'apple-ii', 'apple-ii-primary', 'apple-ii-0'),
        ('kreativekorp/APL2ALT1.TXT', 'apple-ii-alternate-1', 'apple-ii-1'),
        ('kreativekorp/APL2ALT2.TXT', 'apple-ii-alternate-2', 'apple-ii-2'),
        ('kreativekorp/APL2ICHG.TXT', 'apple-ii-chr',),
        ('kreativekorp/ATARI8VG.TXT', 'atascii'),
        ('kreativekorp/ATARI8IG.TXT', 'atascii-chr',),
        ('kreativekorp/ATARI8VI.TXT', 'atascii-international'),
        ('kreativekorp/ATARI8II.TXT', 'atascii-international-chr'),
        ('kreativekorp/ATARISTV.TXT', 'atari-st'),
        # subset of atari-st
        #('kreativekorp/ATARISTI.TXT', 'atari-st-chr',),
        ('kreativekorp/COCOICHG.TXT', 'trs80-coco-sg4-chr', 'coco-sg4-chr'),
        ('kreativekorp/COCOSGR4.TXT', 'trs80-coco-sg4', 'coco-sg4', 'coco-semigraphics-4'),
        ('kreativekorp/COCOSGR6.TXT', 'trs80-coco-sg6', 'coco-sg6', 'coco-semigraphics-6'),
        ('kreativekorp/CPETVPRI.TXT', 'pet', 'pet-primary', 'pet-0'),
        ('kreativekorp/CPETVALT.TXT', 'pet-alternate', 'pet-alt', 'pet-1'),
        ('kreativekorp/CPETIPRI.TXT', 'pet-chr', 'pet-primary-chr', 'pet-0-chr'),
        ('kreativekorp/CPETIALT.TXT', 'pet-alternate-chr', 'pet-alt-chr', 'pet-1-chr'),
        ('kreativekorp/CVICVPRI.TXT', 'vic-20', 'vic', 'vic-primary', 'vic-0'),
        ('kreativekorp/CVICVALT.TXT', 'vic-20-alternate', 'vic-alt', 'vic-1'),
        ('kreativekorp/CVICIPRI.TXT', 'vic-20-chr', 'vic-chr', 'vic-primary-chr', 'vic-0-chr'),
        ('kreativekorp/CVICIALT.TXT', 'vic-20-alternate-chr', 'vic-alt-chr', 'vic-1-chr'),
        ('kreativekorp/C64VPRI.TXT', 'c64', 'c64-primary', 'c64-0'),
        ('kreativekorp/C64VALT.TXT', 'c64-alternate', 'c64-alt', 'c64-1'),
        ('kreativekorp/C64IPRI.TXT', 'c64-chr', 'c64-primary-chr', 'c64-0-chr'),
        ('kreativekorp/C64IALT.TXT', 'c64-alternate-chr', 'c64-alt-chr', 'c64-1-chr'),
        # IBMPCVID.TXT
        # IBMPCICH.TXT
        ('kreativekorp/MINITLG0.TXT', 'minitel-g0', 'minitel-g2'),
        ('kreativekorp/MINITLG1.TXT', 'minitel-g1',),
        ('kreativekorp/MSX.TXT', 'msx-international', 'msx',),
        ('kreativekorp/ORICG0.TXT', 'tangerine-oric-g0', 'oric-g0',),
        ('kreativekorp/ORICG1.TXT', 'tangerine-oric-g1', 'oric-g1',),
        # subset of riscos
        # RISCOSI.TXT
        ('kreativekorp/RISCOSV.TXT', 'risc-os', 'acorn-risc-os', 'risc-os-latin1'),
        ('kreativekorp/RISCOSB.TXT', 'bbc-master', 'risc-os-bfont',),
        ('kreativekorp/RISCEFF.TXT', 'risc-os-eff'),
        ('kreativekorp/SINCLRQL.TXT', 'sinclair-ql',),
        ('kreativekorp/TELTXTG0.TXT', 'teletext-g0', 'teletext'),
        ('kreativekorp/TELTXTG1.TXT', 'teletext-g1',),
        ('kreativekorp/TELTXTG2.TXT', 'teletext-g2',),
        ('kreativekorp/TELTXTG3.TXT', 'teletext-g3',),
        ('kreativekorp/TI994A.TXT', 'ti-99-4a',),
        ('kreativekorp/TRSM1ORG.TXT', 'trs-80', 'trs-80-model1',),
        ('kreativekorp/TRSM1REV.TXT', 'trs-80-revised', 'trs-80-model1-revised',),
        ('kreativekorp/TRSM1ICH.TXT', 'trs-80-chr', 'trs-80-model1-chr',),
        ('kreativekorp/TRSM3VIN.TXT', 'trs-80-model3',),
        ('kreativekorp/TRSM3VJP.TXT', 'trs-80-model3-jp', 'trs-80-model3-katakana'),
        ('kreativekorp/TRSM3VRV.TXT', 'trs-80-model3-reverse'),
        # these replace graphicals at 00-1F with controls
        # TRSM3IIN.TXT
        # TRSM3IJP.TXT
        # TRSM3IRV.TXT
        ('kreativekorp/TRSM4AVP.TXT', 'trs-80-model4a', 'trs-80-model4a-primary', 'trs-80-model4a-0'),
        ('kreativekorp/TRSM4AVA.TXT', 'trs-80-model4a-alternate', 'trs-80-model4a-1'),
        ('kreativekorp/TRSM4AVR.TXT', 'trs-80-model4a-reverse',),
        # TRSM4AIP
        # TRSM4AIA
        # TRSM4AIR
        ('kreativekorp/ZX80.TXT', 'zx80',),
        ('kreativekorp/ZX81.TXT', 'zx81',),
        ('kreativekorp/ZXSPCTRM.TXT', 'zx-spectrum',),
        ('kreativekorp/ZXDESKTP.TXT', 'zx-spectrum-desktop',),
        # ZXFZXPUA.TXT
        ('kreativekorp/ZXFZXLT1.TXT', 'fzx-latin1',),
        ('kreativekorp/ZXFZXLT5.TXT', 'fzx-latin5',),
        ('kreativekorp/ZXFZXKOI.TXT', 'fzx-koi8',),
        ('kreativekorp/ZXFZXSLT.TXT', 'fzx-cp1252',),

        # manually adapted
        ('manual/ms-linedraw.txt', 'windows-linedraw', 'microsoft-linedraw', 'ms-linedraw'),
        ('manual/hp48.txt', 'hp-48', 'hp48', 'hp-rpl'),
        ('manual/iso2047.txt', 'iso-2047'),
        ('manual/c0-pictures.txt', 'control-pictures'),

        # Mozilla Taiwan
        # Big5-ETen
        ('moztw/eten.txt', 'big5-eten', 'eten',),
        # Big5-2003
        ('moztw/big5-2003-b2u.txt', 'big5'),
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
        ('dkuug/iso646-us', 'ascii', 'iso646-us', 'ascii-0', 'us-ascii', 'iso-ir-6', 'ansi-x3.4-1968', 'windows-20127'),
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
        ('dkuug/jis_x0201', 'jis-x0201', 'jis-c-6220'),
        # ibm-897 extends jis-x0201, overlaid below
        ('dkuug/jis_x0201', 'cp897', 'ibm-897'),
        ('dkuug/x0201-7', 'x0201-7', 'iso-ir-13'),

        # charmaps from IBM/Unicode ICU project
        ('icu/ibm-1125_P100-1997.ucm', 'ruscii', 'ibm-1125', 'cp866u', 'cp866nav'),
        ('icu/ibm-720_P100-1997.ucm', 'cp720', 'ibm-720', 'transparent-asmo'),
        ('icu/ibm-858_P100-1997.ucm', 'cp858', 'ibm-858', 'cp850-euro'),
        ('icu/ibm-868_P100-1995.ucm', 'cp868', 'ibm-868', 'cp-ar', 'dos-urdu'),
        ('icu/ibm-851_P100-1995.ucm', 'cp851', 'ibm-851', 'oem-851'),
        # glibc and many others use gbk as an alias of windows-936, though apparently it's complicated
        ('icu/windows-936-2000.ucm', 'windows-936', 'ibm-1386', 'windows-gb2312', 'windows-gbk', 'gbk', 'gbk-0'),
        ('icu/ibm-1375_P100-2008.ucm', 'big5-hkscs', 'ibm-1375', 'big5hk', 'big5hkscs-0'),
        ('icu/ibm-806_P100-1998.ucm', 'cp806', 'ibm-806', 'ibm-iscii-devanagari'),
        # ksc5601-1992-3 is here because Unix/BDF call the Johab encoding ksc5601.1992-3
        # but it's Annex 3, i.e. not the main form of ks-c-5601
        ('icu/windows-1361-2000.ucm', 'windows-1361', 'johab', 'ksc5601-1992-3'),
        # ksc5601.1992-0 would map here
        ('icu/aix-KSC5601.1987_0-4.3.6.ucm', 'ks-c-5601', 'ksc5601-1987', 'ksc5601-1992', 'wansung'),
        # P12A variant has backslash, tilde; P120 has yen, overline
        ('icu/ibm-932_P120-1999.ucm', 'ibm-932',),
        # CNS11643 - note that this has plane 15 (2007 standard) encoded as plane 9. Planes 10-14 (2007) are not included.
        ('icu/cns-11643-1992.ucm', 'cns-11643', 'csic'),
        # EUC-TW, looks like this is algorithmically related to CNS-11643
        #('icu/euc-tw-2014.ucm', 'euc-tw',),

        # from IBM CDRA tables
        # MS-DOS Korean
        # IBM-934 = IBM-891 (sbcs) + IBM-926 (dbcs)
        # https://web.archive.org/web/20101210051426/http://www-01.ibm.com/software/globalization/ccsid/ccsid934.html
        ('ibm-cdra/037B34B0.UPMAP100', 'cp891', 'ibm-891'),
        ('ibm-cdra/039E44B0.UPMAP101', 'cp926', 'ibm-926', 'cp934', 'ibm-934'),
        # MS-DOS Traditional Chinese
        # IBM-938 = IBM-904 (sbcs) + IBM-927 (dbcs)
        # https://web.archive.org/web/20141202002059/http://www-01.ibm.com/software/globalization/ccsid/ccsid938.html
        # "CCSID 948 is a superset of this CCSID."
        ('ibm-cdra/038834B0.UPMAP100', 'cp904', 'ibm-904'),
        ('ibm-cdra/039F34B0.UPMAP100', 'cp927', 'ibm-927', 'cp938', 'ibm-938'),
    )),

    ('ucp', {}, (
        # manually constructed based on gif images
        # https://web.archive.org/web/20061017214053/http://www.cyrillic.com/ref/cyrillic/
        ('manual/russup3.ucp', 'dos-russian-support-3', 'rs3', 'russup3'),
        ('manual/russup4ac.ucp', 'dos-russian-support-4-academic', 'rs4ac', 'russup4ac'),
        ('manual/russup4na.ucp', 'dos-russian-support-4', 'rs4', 'russup4na'),
        # manually rearranged from dec-special charmap
        ('manual/dec-vt100.ucp', 'dec-vt100', 'vt-100'),
    )),

    ('html', {}, (
        # national character sets
        ('wikipedia/mazovia.html', 'mazovia', 'cp667', 'cp790', 'cp991'),
        ('wikipedia/kamenicky.html', 'kamenicky', 'kamenický', 'nec-867', 'keybcs2', 'dos-895'),
        ('wikipedia/cwi2.html', 'cwi-2', 'cwi', 'cp-hu', 'hucwi', 'hu8cwi2'),
        ('wikipedia/pascii.html', 'pascii',),
        ('wikipedia/cp853.html', 'cp853', 'ibm-853'),
        ('wikipedia/brascii.html', 'brascii', 'abnt', 'star-3847'),
        ('wikipedia/abicomp.html', 'abicomp', 'star-3848'),

        # vendor character sets
        # dec-special - this should be underlaid with ascii
        ('wikipedia/dec-special.html', 'dec-special', 'ibm-1090'),
        ('wikipedia/dec-technical.html', 'dec-technical', 'dec-tcs', 'tcs'),
        ('wikipedia/lics.html', 'lotus-international', 'lics'),
        ('wikipedia/ventura.html', 'ventura-international', 'ventura'),

        # font-specific
        ('wikipedia/wingdings.html', 'wingdings', 'windows-wingdings', 'microsoft-wingdings'),

        # platform-specific charmaps
        ('wikipedia/gem.html', 'gem',),
        ('wikipedia/wiscii.html', 'wiscii', 'wang'),
        ('wikipedia/mattel-aquarius.html', 'mattel-aquarius'),
    )),

    # https://vietstd.sourceforge.net/document/unicode.html
    ('txt', dict(codepoint_column=0, unicode_column=2, codepoint_base=10), (
        ('vietstd/viscii1.1.txt', 'viscii', 'viscii1.1-1'),
    )),

    # https://www.unicode.org/Public/MAPPINGS/OBSOLETE/EASTASIA/JIS/JIS0208.TXT
    ('txt', dict(codepoint_column=1, unicode_column=2), (
        ('misc/JIS0208.TXT', 'jisx0208'),
    )),

    # IBM OS/2 Universal Glyph List
    # https://www.borgendale.com/glyphs.htm
    ('txt',
    dict(
            codepoint_column=0, unicode_column=3, comment=';',
            codepoint_base=10, inline_comments=False, ignore_errors=True,
    ), (
        ('misc/ibm-ugl.txt', 'ibm-ugl'),
    )),

    # Windows-1252 extensions
    ('html', dict(table=1), (
        ('wikipedia/windows-1252.html', 'windows-extended', 'ibm-1004', 'os2-1004'),
    )),
    ('html', dict(table=2), (
        ('wikipedia/windows-1252.html', 'windows-1252-msdos'),
    )),
    ('html', dict(table=3), (
        ('wikipedia/windows-1252.html', 'palm-os'),
    )),

    ('html', dict(table=1), (
        ('wikipedia/ventura.html', 'pcl-ventura-international', 'pcl-ventura'),
    )),

    # Dashen codepage
    ('txt', dict(unicode_column=1, codepoint_column=2, separator='\t'), (
        ('misc/dashen-map.txt', 'dashen'),
    )),
)

# charmaps to be overlaid with IBM graphics in range 0x00--0x1f and 0x7f
_ASCII_RANGE = range(0x80)
_ANSI_RANGE = range(0x100)
# iso 8859-1, excluding controls
_ISO_RANGE = tuple(range(0x20, 0x7f)) + tuple(range(0xa0, 0x100))
_IBM_GRAPH_RANGE = tuple(range(0x20)) + (0x7f,)
_MAC_GRAPH_RANGE = range(0x11, 0x15)
_0XDB = (0xDB,)
_0X9C = (0x9C,)
_MAC_CYRILLIC = (0xA2, 0xB6, 0xFF)
_OVERLAYS = (
    # these were partially defined, complete them by adding 7-bit ascii codepoints
    ('iso-8859/8859-1.TXT', _ASCII_RANGE, 'txt', {}, (
        'koi8-a', 'koi8-b', 'koi8-e', 'koi8-f', 'gost-19768-87', 'mik',
        # per NEXTSTEP.TXT, identical to ascii.
        # wikipedia suggests it's us-ascii-quotes
        'next',
        'rs3', 'rs4', 'rs4ac', 'mazovia', 'kamenicky', 'cwi-2', 'viscii',
        'cp853', 'suneu-greek', 'mule-lao', 'dec-vt100',
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
    # ibm-897 == jis-x0201 with graphics
    # constructed based on https://en.wikipedia.org/wiki/Code_page_897
    ('manual/ibm897graph.ucp', _IBM_GRAPH_RANGE, 'ucp', {}, (
        'cp897', 'ibm-943',
    )),
    # Mac OS system fonts and euro vs currency sign
    ('manual/mac-system.ucp', _MAC_GRAPH_RANGE, 'ucp', {}, ('mac-roman', 'mac-roman-8.5')),
    ('manual/currency-sign-0xdb.ucp', _0XDB, 'ucp', {}, (
        'mac-roman', 'mac-celtic', 'mac-icelandic', 'mac-croatian', 'mac-gaelic', 'mac-romanian',
    )),
    ('manual/currency-sign-0x9c.ucp', _0X9C, 'ucp', {}, ('mac-greek',)),
    ('manual/mac-cyrillic-pre9.0.ucp', _MAC_CYRILLIC, 'ucp', {}, ('mac-cyrillic',)),
    ('manual/mac-ukrainian-pre9.0.ucp', _MAC_CYRILLIC, 'ucp', {}, ('mac-ukrainian',)),
    # there's a different ordering of the ibm graphics range specially for cp864
    ('misc/IBMGRAPH.TXT', _IBM_GRAPH_RANGE, 'txt', dict(
        codepoint_column=2, unicode_column=0
    ), ('cp864',)),
    ('microsoft/WINDOWS/CP1252.TXT', _ISO_RANGE, 'txt', {}, ('windows-extended', 'palm-os')),
    ('iso-8859/8859-1.TXT', _ANSI_RANGE, 'txt', {}, ('windows-1252-msdos',)),
    # IBM combined codepages SBCS page
    ('ibm-cdra/037B34B0.UPMAP100', _ANSI_RANGE, 'ucm', {}, ('cp934',)),
    ('ibm-cdra/038834B0.UPMAP100', _ANSI_RANGE, 'ucm', {}, ('cp938',)),
)
