This directory contains mappings of legacy character sets from popular 8-bit
and 16-bit microcomputers as well as teletext to Unicode. Most of these
mappings are made possible using characters from the "Proposal to add
characters from legacy computers and teletext to the UCS".

Some of these systems have two kinds of mappings: a "video" or "memory" mapping
that reflects how bytes in video memory are mapped to characters, and an
"interchange" or "CHR$()" mapping that reflects how keyboard input, the BASIC
CHR$() function, or external I/O maps code values to characters. Either kind of
mapping may be needed depending on the use case.

The following systems are represented here along with notes. All trademarks and
registered trademarks are the property of their respective owners. The company
and product names used here are for identification purposes only.


Coleco Adam

ADAMOS7.TXT: Coleco Adam OS7 character set.
ADAMSWTR.TXT: Coleco Adam SmartWRITER character set.

The OS7 character set includes characters at $05-$1C that compose a graphic
that spells COLECOVISION. These have been mapped to characters in the Private
Use Area.

The SmartWRITER character set includes two unidentified characters at $08 and
$09 which have also been mapped to characters in the Private Use Area.


Amstrad CPC

AMSCPC.TXT: Amstrad CPC character set.

The Amstrad CPC character set contains three unidentified characters at $EF,
$FC, and $FD which have been mapped to characters in the Private Use Area.


Amstrad CP/M Plus, PCW, and ZX Spectrum 3+

AMSCPM.TXT: Amstrad CP/M Plus, PCW, and ZX Spectrum 3+ character set.

The slashed zero at $30 is mapped to U+0030+FE00, the recently-added
standardized variation sequence for a slashed zero. The non-slashed
zero at $7F is mapped to U+0030.


Apple II series

APL2PRIM.TXT: Apple II primary character set as mapped in memory.
APL2ALT1.TXT: Apple II alternate character set, version 1, as mapped in memory.
APL2ALT2.TXT: Apple II alternate character set, version 2, as mapped in memory.
APL2ICHG.TXT: Apple II character set as mapped by CHR$().

Version 1 of the alternate character set has the "running man" characters where
version 2 of the alternate character set has the "inverse return arrow" and
"title bar" characters.

Both versions of the alternate character set include a solid Apple logo at $40
and an open Apple logo at $41. Since the Apple logo is trademarked and thus
cannot be encoded, these are mapped to characters in the Private Use Area.


Atari 8-bit series (ATASCII)

ATARI8VG.TXT: ATASCII graphics character set, memory-mapped.
ATARI8IG.TXT: ATASCII graphics character set, CHR$()-mapped.
ATARI8VI.TXT: ATASCII international character set, memory-mapped.
ATARI8II.TXT: ATASCII international character set, CHR$()-mapped.

The graphics character set has symbols and semigraphics where the international
character set has precomposed Latin characters with diacritics.

The CHR$() mappings are in a different order and do not include the control
characters at $1B-$1F, $7D-$7F, $8B-$8F, and $FD-$FF.


Atari ST

ATARISTV.TXT: Atari ST character set, memory-mapped.
ATARISTI.TXT: Atari ST character set, CHR$()-mapped.

The Atari ST character set is based on and similar to IBM PC code page 437, but
has different characters in some locations, in particular $00-$1F and $B0-$DF.

The CHR$() mapping is identical to the memory mapping except it does not
include the control characters at $00-$1F and $7F.

The Atari ST character set includes an Atari logo at $0E-$0F and an image of
J.R. "Bob" Dobbs at $1C-$1F. Both are trademarked and unsuitable for encoding,
so these are mapped to characters in the Private Use Area.


TRS-80 Color Computer

COCOICHG.TXT: TRS-80 Color Computer "Semigraphics 4" set as mapped by CHR$().
COCOSGR4.TXT: TRS-80 Color Computer "Semigraphics 4" set as mapped in memory.
COCOSGR6.TXT: TRS-80 Color Computer "Semigraphics 6" set as mapped in memory.

The Color Computer, despite being branded as a TRS-80, is a fundamentally
different computer. The "Semigraphics 4" mode, which is default, has a
character set organized thusly:

$00 - $1F - light-on-dark ASCII-1983 uppercase
$20 - $3F - light-on-dark ASCII-1983 punctuation
$40 - $5F - dark-on-light ASCII-1983 uppercase
$60 - $7F - dark-on-light ASCII-1983 punctuation
$80 - $FF - 2x2 block graphics in 8 colors

(The 8 colors are, in order: green, yellow, blue, red, buff, cyan, magenta,
and orange.)

The CHR$() function uses this mapping:

Interchange => Video
$00 - $1F => (control characters)
$20 - $3F => $60 - $7F (dark-on-light punctuation)
$40 - $5F => $40 - $5F (dark-on-light uppercase)
$60 - $7F => $00 - $1F (light-on-dark uppercase)
$80 - $FF => $80 - $FF (2x2 block graphics in 8 colors)

The "Semigraphics 6" mode has 2x3 block graphics at $80-$FF in two colors (blue
and red), although in a different order from Teletext and the TRS-80. ($00-$7F
displays as binary vertical line garbage, which is pretty much useless and
unworthy of encoding.)


Commodore PET (PETSCII)

CPETVPRI.TXT: Commodore PET primary character set as mapped in memory.
CPETVALT.TXT: Commodore PET alternate character set as mapped in memory.
CPETIPRI.TXT: Commodore PET primary character set as mapped by CHR$().
CPETIALT.TXT: Commodore PET alternate character set as mapped by CHR$().

The PET has REVERSE SOLIDUS where the VIC-20, C64, and C128 have POUND SIGN.
The PET and VIC-20 have CHECKER BOARD FILL where the C64 and C128 have
INVERSE CHECKER BOARD FILL, and vice-versa.

The primary character set has uppercase letters where the alternate character
set has lowercase letters. The primary character set has semigraphics
characters where the alternate character set has uppercase letters.

The CHR$() function mapping (or "interchange" mapping) maps to the in-memory
mapping (or "video" mapping) as follows:

Interchange => Video
$00 - $1F => (control characters)
$20 - $3F => $20 - $3F
$40 - $5F => $00 - $1F
$60 - $7F => $40 - $5F
$80 - $9F => (control characters)
$A0 - $BF => $60 - $7F
$C0 - $DF => $40 - $5F
$E0 - $FF => $60 - $7F


Commodore VIC-20 (PETSCII)

CVICVPRI.TXT: Commodore VIC-20 primary character set as mapped in memory.
CVICVALT.TXT: Commodore VIC-20 alternate character set as mapped in memory.
CVICIPRI.TXT: Commodore VIC-20 primary character set as mapped by CHR$().
CVICIALT.TXT: Commodore VIC-20 alternate character set as mapped by CHR$().

The same notes that apply to the Commodore PET apply to the Commodore VIC-20.


Commodore 64 and Commodore 128 (PETSCII)

C64VPRI.TXT: Commodore 64 and 128 primary character set as mapped in memory.
C64VALT.TXT: Commodore 64 and 128 alternate character set as mapped in memory.
C64IPRI.TXT: Commodore 64 and 128 primary character set as mapped by CHR$().
C64IALT.TXT: Commodore 64 and 128 alternate character set as mapped by CHR$().

The same notes that apply to the Commodore PET apply to the Commodore 64 and
Commodore 128.


IBM PC (code page 437)

IBMPCVID.TXT: IBM PC code page 437 as mapped in memory.
IBMPCICH.TXT: IBM PC code page 437 without control characters.

IBMPCVID.TXT includes the graphics characters at $00-$1F and $7F that are
instead mapped to control characters in the mapping provided by Microsoft.
IBMPCICH.TXT is identical to the mapping provided by Microsoft but does not
explicitly list the control characters.


Minitel

MINITLG0.TXT: Minitel G0/G2 text character set.
MINITLG1.TXT: Minitel G1 graphics character set.

The G0 mapping also includes G2 characters using the SS2 (single shift 2)
control character ($19). The G1 character set is similar to the Teletext G1
character set.


MSX

MSX.TXT: MSX international character set.

The MSX character set is based on CP437 but has some additional punctuation
and precomposed letters and a different set of box drawing and block element
characters. There is also a set of extended graphic characters accessed with
double-byte sequences starting with $01.


Tangerine Oric series (OricSCII)

ORICG0.TXT: Tangerine Oric G0 text character set.
ORICG1.TXT: Tangerine Oric G1 graphics character set.

The G1 character set includes user-defined characters at $60-$7F which have
been mapped to the Private Use Area. The user-defined characters at $70-$7F
are normally unusable due to the character generator RAM overlapping the
text screen RAM.


RISC OS

RISCOSI.TXT: RISC OS Latin-1 character set.
RISCOSV.TXT: RISC OS Latin-1 character set with RISC OS-specific characters.
RISCOSB.TXT: RISC OS BFont character set.
RISCEFF.TXT: RISC OS Latin-1 character set used by Electronic Font Foundry.

The RISC OS character set is based on ISO Latin-1 with extra characters at
$80-$9F. RISCOSV.TXT includes characters specific to the RISC OS user interface
not included in RISCOSI.TXT. RISCEFF.TXT is similar to RISCOSI.TXT but with
additional characters and a different mapping used by Electronic Font Foundry,
a third-party supplier of RISC OS fonts.

RISCOSB.TXT is a separate encoding not based on ISO Latin-1 called the BFont
encoding. According to the RISC OS Programmer's Reference Manual it was used
in the BBC Master microcomputer and is retained in RISC OS for compatibility.


Sinclair QL

SINCLRQL.TXT: Sinclair QL character set.

Several of the Sinclair QL character set's glyphs featured raised small capital
letters. These have been mapped to MODIFIER LETTER SMALL A-F due to the absence
of *MODIFIER LETTER CAPITAL C and *MODIFIER LETTER CAPITAL F.

There is a strange character at $B5 that looks like a small capital letter Q
with a V shape underneath. I've mapped this to a capital letter Q with a
combining caron below as the closest possible match.


Teletext

TELTXTG0.TXT: Teletext G0 English alphanumerics character set.
TELTXTG1.TXT: Teletext G1 English graphics character set.
TELTXTG2.TXT: Teletext G2 Latin Supplementary Set.
TELTXTG3.TXT: Teletext G3 Smooth Mosaics and Line Drawing Set.

See European Telecommunication Standard 300 706 for details.


Texas Instruments TI-99/4a

TI994A.TXT: TI-99/4a character set.

The TI-99/4a character set is mostly US-ASCII, except it includes two special
characters at $1E and $1F and user-defined characters at $7F-$9F. $1E is the
cursor character, which is mapped to FULL BLOCK. $1F is a block the color of
the screen border, which, because of how the TI-99/4a's video actually works,
is best mapped to NO-BREAK SPACE. $7F-$9F are mapped to the Private Use Area.


TRS-80 Model I

TRSM1ORG.TXT: TRS-80 Model I, original version, as mapped in memory.
TRSM1REV.TXT: TRS-80 Model I, revised version, as mapped in memory.
TRSM1ICH.TXT: TRS-80 Model I as mapped by CHR$() (same for both revisions).

The original version has an opening quotation mark, lowercase letters without
descenders, and a tilde where the revised version has a pound sign, lowercase
letters with descenders, and a yen sign. The CHR$() mapping does not have these
characters at all; it duplicates the uppercase region of the character set
instead.


TRS-80 Model III and Model 4

TRSM3VIN.TXT: TRS-80 Model III/4 international set as mapped in memory.
TRSM3VJP.TXT: TRS-80 Model III/4 katakana set as mapped in memory.
TRSM3VRV.TXT: TRS-80 Model III/4 reverse video set as mapped in memory.
TRSM3IIN.TXT: TRS-80 Model III/4 international set as mapped by CHR$().
TRSM3IJP.TXT: TRS-80 Model III/4 katakana set as mapped by CHR$().
TRSM3IRV.TXT: TRS-80 Model III/4 reverse video set as mapped by CHR$().

The IN and JP sets both have semigraphics at $80-$BF, but the IN set has
miscellaneous symbols at $C0-$FF whereas the JP set has halfwidth katakana.
The RV set has no semigraphics at all, but instead has reverse-video versions
of $00-$7F at $80-$FF. The CHR$() mapping of each set is nearly identical to
the corresponding memory mapping but has control characters at $00-$1F instead
of graphics characters.

The Model III and Model 4 include an unidentified character at $FB which has
been mapped to a character in the Private Use Area.


TRS-80 Model 4a

TRSM4AVP.TXT: TRS-80 Model 4a primary character set as mapped in memory.
TRSM4AVA.TXT: TRS-80 Model 4a alternate character set as mapped in memory.
TRSM4AVR.TXT: TRS-80 Model 4a reverse video set as mapped in memory.
TRSM4AIP.TXT: TRS-80 Model 4a primary character set as mapped by CHR$().
TRSM4AIA.TXT: TRS-80 Model 4a alternate character set as mapped by CHR$().
TRSM4AIR.TXT: TRS-80 Model 4a reverse video set as mapped by CHR$().

The Model 4 and Model 4a have completely different characters at $00-$1F.
Otherwise, the primary character set of the Model 4a is identical to the
international set of the Model 4; however, the Model 4a does not have a
katakana set and instead has an alternate character set with some Latin-1
characters and a completely different set of miscellaneous symbols.

The Model 4a includes two unidentified characters at $1D and $FB which have
been mapped to characters in the Private Use Area.


Sinclair ZX80, ZX81, and ZX Spectrum

ZX80.TXT: Sinclair ZX80 character set.
ZX81.TXT: Sinclair ZX81 character set.
ZXSPCTRM.TXT: Sinclair ZX Spectrum character set.
ZXDESKTP.TXT: Sinclair ZX Spectrum "Desktop" character set.
ZXFZXPUA.TXT: "FZX" character set with $80-$FF mapped to the Private Use Area.
ZXFZXLT1.TXT: "FZX" character set with $A0-$FF mapped to Latin-1 (ISO 8859-1).
ZXFZXLT5.TXT: "FZX" character set with $A0-$FF mapped to Latin-5 (ISO 8859-9).
ZXFZXKOI.TXT: "FZX" character set with $A0-$FF mapped to KOI-8.
ZXFZXSLT.TXT: "FZX" character set with $80-$FF mapped to CP1252.

The ZX80 and ZX81 character sets are only defined over $00-$3F and $80-$BF.
Other code values are used for control characters or BASIC tokens and have no
mapping to any visible character. The ZX80 and ZX81 have the same printable
characters but in a different order.

The ZX Spectrum character set, unlike the ZX80 and ZX81 character sets, is
based on ASCII. It includes semigraphics at $80-$8F and user-defined characters
at $90-$A4. Characters beyond $A4 are used for BASIC tokens and have no mapping
to any visible character. The user-defined characters have been mapped to the
Private Use Area.

"Desktop" is a word processing program for the ZX Spectrum published in 1991
by Proxima Software. It uses its own font files with precomposed characters at
$80-$9D to support Czech.

"FZX" is a royalty-free font format for the ZX Spectrum released in 2013 by
Andrew Owen and Einar Saukas. The FZX specification supports but does not
define the encoding for characters $80-$FF. Most FZX fonts that include these
characters use Latin-1 (ISO 8859-1), Latin-5 (ISO 8859-9), or KOI-8.
