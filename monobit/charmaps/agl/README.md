https://github.com/adobe-type-tools/agl-aglfn/

# AGL & AGLFN

This open source project is intended to be coupled with the [AGL Specification](https://github.com/adobe-type-tools/agl-specification), and provides the resources that it references.

## Contents

This project includes the following three resources:

* AGL (*glyphlist.txt*)
* AGLFN (*aglfn.txt*)
* ITC Zapf Dingbats Glyph List (*zapfdingbats.txt*)

## Overview

AGL (*Adobe Glyph List*) simply provides mappings from glyph names to Unicode scalar values.

AGLFN (*Adobe Glyph List For New Fonts*) provides a list of base glyph names that are recommended for new fonts, which are compatible with the [AGL (*Adobe Glyph List*) Specification](https://github.com/adobe-type-tools/agl-specification), and which should be used as described in Section 6 of that document. AGLFN comprises the set of glyph names from AGL that map via the AGL Specification rules to the semantically correct UV (*Unicode Value*). For example, 'Asmall' is omitted because AGL maps this glyph name to the PUA (*Private Use Area*) value U+F761, rather than to the UV that maps from the glyph name 'A'. Also omitted is 'ffi', because AGL maps this to the Alphabetic Presentation Forms value U+FB03, rather than decomposing it into the following sequence of three UVs: U+0066, U+0066, and U+0069. The name 'arrowvertex' has been omitted because this glyph now has a real UV, and AGL is now incorrect in mapping it to the PUA value U+F8E6. If you do not find an appropriate name for your glyph in this list, then please refer to Section 6 of the AGL Specification.

The *ITC Zapf Dingbats Glyph List* is similar to AGL in that it simply provides mappings from glyph names to Unicode scalar values, but only for glyphs in the ITC Zapf Dingbats font.

## Format

Each record in AGL (*glyphlist.txt*) and the *ITC Zapf Dingbats Glyph List* (*zapfdingbats.txt*) is comprised of two semicolon-delimited fields, described as follows:

* Glyph name—*upper/lowercase letters and digits*
* Unicode scalar value—*four uppercase hexadecimal digits*

The AGL and *ITC Zapf Dingbats Glyph List* records are sorted by glyph name in increasing ASCII order, lines starting with '#' are comments, and blank lines should be ignored.

Each record in AGLFN (*aglfn.txt*) is comprised of three semicolon-delimited fields, described as follows:

* Standard UV or CUS (*Corporate Use Subarea*) UV—*four uppercase hexadecimal digits*
* Glyph name—*upper/lowercase letters and digits*
* Character names: Unicode character names for standard UVs, and descriptive names for CUS UVs—*uppercase letters, hyphen, and space*

The AGLFN records are sorted by glyph name in increasing ASCII order, entries with the same glyph name are sorted in decreasing priority order, the UVs and Unicode character names are provided for convenience, lines starting with '#' are comments, and blank lines should be ignored.

## More Information

Important details about glyph naming and interpreting glyph names can be found in the [AGL Specification](https://github.com/adobe-type-tools/agl-specification), which is an open specification.

The tools and documentation that comprise [AFDKO (*Adobe Font Development Kit for OpenType*)](https://github.com/adobe-type-tools/afdko/) are helpful for those who develop OpenType fonts. For general and format-related questions about OpenType fonts, the [OpenType Specification](https://docs.microsoft.com/en-us/typography/opentype/spec/) is the single best source.

## Getting Involved

Suggest changes by creating a new [issue](https://github.com/adobe-type-tools/agl-aglfn/issues).
