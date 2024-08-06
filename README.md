
    -@@------------------------------------------@@------@@--------------@@-
    -@@------------------------------------------@@------@@--@@----------@@-
    -@@------------------------------------------@@----------@@----------@@-
    -@@------@@@@@@@@@----@@@@---@@@@@----@@@@---@@@@@---@@-@@@@---------@@-
    -@@------@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@----------@@-
    -@@------@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@----------@@-
    -@@------@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@----------@@-
    -@@------@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@----------@@-
    -@@------@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@--@@------@@-
    -@@------@@--@@--@@---@@@@---@@--@@---@@@@---@@@@@---@@---@@-@@------@@-
    -@@------------------------------------------------------------------@@-
    -@@------------------------------------------------------------------@@-
    -@@------------------------------------------------------------------@@-


Tools for working with monochrome bitmap fonts
==============================================

The `monobit` tools let you modify bitmap fonts and convert between several formats.

`monobit`'s native format is `yaff`, a human-friendly, text-based visual format similar to the ones used by
Roman Czyborra's `hexdraw`, Simon Tatham's `mkwinfont` and John Elliott's `psftools`. Details are
given in [the `yaff` font file format specification](YAFF.md).

Monobit requires Python 3.9 or above. Install through `pip install monobit`. Some formats or features require additional packages; see _Dependencies_ below for a list. These
will be installed automatically if you use `pip`.

`monobit` can be used as a Python package or as a command-line tool.



Usage examples
--------------

##### Convert utility

Here are some examples of how to use the conversion utility.

`monobit-convert --help`

Display usage summary and command-line options

`monobit-convert --help load --format=raw`

Display usage summary and additional format-specific command-line options for conversion from raw binary.

`monobit-convert fixedsys.fon`

Recognise the source file format from "magic bytes" or suffix (here, a Windows font) and write fonts
to standard output in `yaff` format.

`monobit-convert roman.bdf to --format=unifont`

Read font from BDF file and write to standard output as Unifont HEX.

`monobit-convert fixed.psf to fixed.png`

Read font in PSF format and write to disk as image in PNG format.

`monobit-convert --format=c to --format=bdf`

Read font from standard input as C-source coded binary and write to standard output as BDF.

The converter transparently reads and writes `gz`, `bz2`, or `xz`-compressed font files and can read
and write `zip` and `tar` archives. Some font formats contain multiple fonts whereas others can
contain only one; the converter will write multiple files to a directory or archive if needed.

It is also possible to apply various transformations on the font before saving it. Check
`monobit-convert --help` for usage.


##### Banner utility

The banner utility renders text to standard output in a given font. This is similar to the ancient
`banner` commands included in System-V and BSD Unixes.

For example, the banner at the top of this `README` was made with

    me@bandit:~$ monobit-banner '| monobit. |' --font=VGASYS.FON

`monobit-banner` has a number of rendering options - you can choose fonts, change the "ink" and "paper"
characters, set a margin, scale text, and rotate by quarter turns.
Check `monobit-banner --help` for usage.


Proportional-spacing formats
----------------------------

| Format                | Short Name | Typical Extension           | Read  | Write | Type   | Features |
|-----------------------|------------|-----------------------------|-------|-------|--------|----------|
| Xerox Alto CONVERT    | `alto`     | `.al`                       |&check;|       | binary | -        |
| Amiga Font Contents   | `amiga-fc` | `.font`                     |&check;|       | binary | Mu       |
| Amiga font            | `amiga`    |                             |&check;|       | binary | O        |
| X11/Adobe BDF         | `bdf`      | `.bdf`                      |&check;|&check;| coded  | U SB MB Ve O |
| Xerox Alto BITBLT     | `bitblt`   | `.strike` `.ks`             |&check;|       | binary | O        |
| AngelCode BMFont [P]  | `bmfont` | `.fnt` `.xml` `.json` + images|&check;|&check;| image  | Mu U SB MB O Ke (CA) |
| FONTRIX (PC), PCPaint, GRASP, ChiWriter | `chiwriter` | `.set` `.[specx]ft` |&check;| | binary | -   |
| Consoleet / vfontas   | `consoleet`| `.txt`                      |&check;|&check;| visual | -        |
| Daisy-Dot             | `daisy`    | `.nlq` `.nl2` `.nl3` `.nl4` |&check;|       | binary | -        |
| DosStart!             | `dosstart` | `.dsf`                      |&check;|&check;| coded  | -        |
| EDWIN bitmap font     | `edwin`    | `.fnt`                      |&check;|&check;| coded  | -        |
| Figlet font           | `figlet`   | `.flf`                      |&check;|&check;| visual | (CA)     |
| FZX font              | `fzx`      | `.fzx`                      |&check;|&check;| binary | O        |
| OS/2 GPI resource     | `gpi`      | `.fnt`                      |&check;|       | binary | SB O (MB Ke) |
| Atari GDOS / GEM      | `gdos`     | `.fnt` `.gft` `.vga`        |&check;|&check;| binary | O        |
| GEOS font file (CVT)  | `geos`     | `.cvt`                      |&check;|&check;| binary | Mu; see `vlir` |
| Adafruit GFX font     | `gfxfont`  | `.h`                        |&check;|&check;| coded  | O        |
| hexdraw               | `hexdraw`  | `.draw`                     |&check;|&check;| visual | U        |
| HP PCL soft font      | `hppcl`    | `.sft` `.sfp` `.sfl`        |&check;|&check;| esc    | SB MB O  |
| Apple IIgs font       | `iigs`     | `.fon`                      |&check;|&check;| binary | see `nfnt` |
| Bitmap image [P]      | `image`    | `.png` `.gif` `.bmp`        |&check;|&check;| image  | -        |
| Set of Bitmap images [P] | `imageset` | `.png` `.gif` `.bmp`     |&check;|&check;| image  | -        |
| LISA font library     | `lisa`     | `.bin`                      |&check;|       | binary | Mu; see `nfnt` |
| MacOS font            | `mac`      | `.dfont` `.suit`            |&check;|&check;| binary | Mu Ke; see `nfnt` |
| MouseGraphics Toolkit | `mgtk`     |                             |&check;|       | binary | -        |
| mkwinfont text format | `mkwinfont`| `.fd`                       |&check;|&check;| visual | SB       |
| Windows or OS/2 font  | `mzfon`    | `.fon` `.exe` `.dll`        |&check;| (1)   | binary | Mu; see `win`, `gpi` |
| Bare NFNT resource    | `nfnt`     | `.f`                        |&check;|&check;| binary | SB O (CA) |
| Palm OS font (v1/NFNT)| `palm`     | `.pdb`                      |&check;|       | binary | Mu; see `nfnt` |
| Palm OS PRC (v1/NFNT) | `palm-prc` | `.prc`                      |&check;|       | binary | Mu; see `nfnt` |
| X11 Portable Compiled Format |  `pcf` | `.pcf`                   |&check;|&check;| binary | U SB MB O |
| PC/GEOS v2.0+         | `pcgeos`   | `.fnt`                      |&check;|&check;| binary | O (MB Ke) |
| PILfont [P]           | `pilfont`  | `.pil` + `.pbm`             |&check;|&check;| image  | O        |
| TeX PKFONT            | `pkfont`   | `.pk`                       |&check;|       | binary | O        |
| Adobe Prebuilt Format | `prebuilt` | `.bepf` `.lepf`             |&check;|       | binary | (Ve CA) |
| Xerox Alto PrePress   | `prepress` | `.ac`                       |&check;|       | binary | O        |
| The Print Shop        | `printshop`| `.pnf`                      |&check;|       | binary | -        |
| Signum! 2             | `signum`   | `.e24` `.p9` `.p24` `.l30`  |&check;|       | binary | -        |
| SFont                 | `sfont`    |                             |&check;|&check;| image  | (CA)     |
| SFNT embedded bitmap  | `sfnt`     | `.otb` `.ttf` `.otf` [F] [**] |&check;| (2) | binary | Mu US SB MB O Ke Ve (CA) |
| SFNT collection       | `ttcf`     | `.otc` `.ttc` [F] [**]      |&check;| (2) | binary | Mu US SB MB O Ke Ve (CA) |
| vfont                 | `vfont`    |                             |&check;|&check;| binary | O        |
| Bare GEOS font record | `vlir`     |                             |&check;|&check;| binary | O        |
| Windows FNT resource  | `win`      | `.fnt`                      |&check;|&check;| binary | SB       |
| monobit yaff          | `yaff`     | `.yaff`                     |&check;|&check;| visual | Mu US SB MB O Ke Ve |

[P] requires **PIL**  
[F] requires **fontTools**  

(1) 16-bit Windows NE container with FNT resource only  
(2) Bitmap only (OTB)  

Mu multiple-font container  
U  Unicode  
US Unicode, multi-codepoint sequences  
SB Single-byte character sets  
MB Multi-byte character sets  
O  Overlapping glyphs
Ke Kerning  
Ve Vertical metrics  
CA Colour / Anti-aliasing (not supported by `monobit`)  

If the abbreviation is bracketed, the format supports this but it is not implemented.


Character-cell formats
----------------------

| Format                | Short Name | Typical Extension           | Read  | Write | Type   | Cell | Features |
|-----------------------|------------|-----------------------------|-------|-------|--------|------|----------|
| 64C                   | `64c`      | `.64c`                      |&check;|&check;| binary | 8x8  | -        |
| +3DOS                 | `plus3dos` |                             |&check;|&check;| binary | 8x8  | -        |
| BBC soft font         | `bbc`      |                             |&check;|&check;| esc    | 8x8  | -        |
| Codepage Information  | `cpi`      | `.cpi`                      |&check;|&check;| binary | 8xN  | Mu SB    |
| Dashen                | `dashen`   | `.pft`                      |&check;|       | binary | any  | -        |
| DEC DRCS soft font    | `dec`      |                             |&check;|&check;| esc    | >4xN | -        |
| Dr. Halo / Dr. Genius | `drhalo`   | `.fon`                      |&check;|       | binary | any  | -        |
| FONTX2                | `fontx`    | `.fnt`                      |&check;|&check;| binary | any  | MB       |
| FONTEDIT              | `fontedit` | `.com`                      |&check;|       | binary | 8xN  | -        |
| Fontraption           | `frapt`    | `.com`                      |&check;|       | binary | 8xN  | -        |
| Fontraption TSR       | `frapt-tsr`| `.com`                      |&check;|       | binary | 8xN  | -        |
| PCPaint, GRASP old format | `grasp`| `.set` `.fnt`               |&check;|&check;| binary | any  | -        |
| Hanzi Bitmap Font     | `hbf`      | `.hbf` + raw binary         |&check;|&check;| binary | any  | SB MB    |
| GNU Unifont           | `unifont`  | `.hex`                      |&check;|&check;| coded  | 8x16 (strict) 8xN<=32 (ext) | MC U (strict) MC US (ext) |
| Bare codepage         | `kbd`      | `.cp`                       |&check;|&check;| binary | 8xN  | SB       |
| LETAFONT loader       | `letafont` | `.com`                      |&check;|       | binary | 8x8  | -        |
| REXXCOM Font Mania    | `mania`    | `.com`                      |&check;|       | binary | 8xN  | -        |
| NetBSD wsfont C header| `netbsd`   | `.h`                        |&check;|&check;| coded  | any  | Mu SB    |
| Optiks PCR Font       | `pcr`      | `.pcr`                      |&check;|&check;| binary | 8xN  | -        |
| PC Screen Font        | `psf`      | `.psf` `.psfu`              |&check;|&check;| binary | any (v2) 8xN (v1) | US  |
| psf2ams PSFCOM        | `psfcom`   | `.com`                      |&check;|       | binary | 8x8, 8x16 | -   |
| psf2txt               | `psf2txt`  | `.txt`                      |&check;|&check;| visual | any  | US       |
| Raw binary            | `raw`      | `.fnt` `.rom` [*]           |&check;|&check;| binary | -    | -        |
| UDG loader            | `udg`      | `.com`                      |&check;|       | binary | 8x8  | -        |
| FreeBSD console font  | `vtfont`   | `.fnt`                      |&check;|&check;| binary | any  | MC U     |
| Hercules Write On!    | `writeon`  | `.wof`                      |&check;|&check;| binary | 8x14 multiples | - |
| NetBSD wsfont binary  | `wsfont`   | `.wsf`                      |&check;|&check;| binary | any  | SB       |
| Wyse-60 soft font     | `wyse`     |                             |&check;|&check;| esc    | 8x16 | -        |
| XBIN font section     | `xbin`     | `.xb`                       |&check;|&check;| binary | 8X<=32 | -        |


MC multi-cell glyphs


Charts (write only)
-------------------

| Format                | Short Name |
|-----------------------|------------|
| Text or blocks        | `chart`    |
| Image [P]             | `chart`    |
| PDF chart [R]         | `pdf`      |

[P] requires **PIL**  
[R] requires **reportlab**  


Stroke (vector) formats
-----------------------

Stroke font support is experimental. Stroke fonts are scalable fonts defined as
line segments. They are fundamentally different from modern fonts in that they
define single strokes whereas modern fonts define outlines to be filled with ink.
Additionally, the fonts currently supported consist of straight line segments only.


| Format                     | Short Name | Typical Extension | Read  | Write |
|----------------------------|------------|-------------------|-------|-------|
| monobit yaff               | `yaff`     | `.yaff`           |&check;|&check;|
| SVG Fonts                  | `svg`      | `.svg`            |&check;|&check;|
| Windows resource           | `win`      | `.fnt`            |&check;|&check;|
| Windows font               | `fon`      | `.fon`            |&check;|&check; (NE) |
| Borland Graphics Interface | `borland`  | `.chr`            |&check;|&check;|
| Hershey fonts (Jim Hurt)   | `hurt`     | `.jhf`            |&check;|       |
| DOSStart                   | `dosstart` | `.dsf`            |&check;|       |
| GIMMS                      | `gimms`    | `.bin`            |&check;|       |


Wrapper formats
-----------------

`monobit` will recurse and extract font files from a number of common container,
archive, compression and encoding formats:

| Format                | Name     | Typical Extension       | Read  | Write |
|-----------------------|----------|-------------------------|-------|-------|
| PKZip/WinZip          | `zip`    | `.zip`                  |&check;|&check;|
| GNU tar               | `tar`    | `.tar` `.tgz`           |&check;|&check;|
| RAR [A]               | `rar`    | `.rar`                  |&check;|       |
| 7-Zip [A]             | `7zip`   | `.7z`                   |&check;|&check;|
| MS Cabinet [A]        | `cabinet`| `.cab`                  |&check;|       |
| LHarc/LHA/LZH [A]     | `lharc`  | `.lha` `.lzh`           |&check;|       |
| ACE [C]               | `ace`    | `.ace`                  |&check;|       |
| ISO 9660 [A]          | `iso9660`| `.iso`                  |&check;|&check;|
| WARC [A]              | `warc`   | `.warc`                 |&check;|&check;|
| CPIO [A]              | `cpio`   | `.cpio`                 |&check;|&check;|
| PAX [A]               | `pax`    | `.pax`                  |&check;|&check;|
| XAR [A]               | `xar`    | `.xar`                  |&check;|&check;|
| AR [A]                | `ar`     | `.ar`                   |&check;|&check;|
| GZip                  | `gzip`   | `.gz`                   |&check;|&check;|
| BZip2                 | `bzip2`  | `.bz2`                  |&check;|&check;|
| XZ/LZMA               | `lzma`   | `.xz` `.lzma`           |&check;|&check;|
| Compress [Z]          | `compress`| `.Z`                   |&check;|&check;|
| AppleSingle           | `apple1` | `.as`                   |&check;|       |
| AppleDouble           | `apple2` | `.adf` `.rsrc`          |&check;|       |
| MacBinary             | `macbin` | `.bin`                  |&check;|       |
| BinHex 4.0            | `binhex` | `.hqx`                  |&check;|       |
| BinSCII               | `binscii`| `.bsc` `.bsq`           |&check;|       |
| Intel Hex             | `intel`  | `.ihex` `.ihx`          |&check;|&check;|
| Base64                | `base64` |                         |&check;|&check;|
| Quoted-printable      | `quopri` |                         |&check;|&check;|
| UUEncode              | `uuencode`|                        |&check;|&check;|
| yEncode [Y]           | `yenc`   |                         |&check;|&check;|
| MIME multipart email  | `email`  | `.eml` `.msg`           |&check;|&check;|
| C or C++ coded binary | `c`      | `.c` `.cpp` `.cc` `.h`  |&check;|&check;|
| JSON coded binary     | `json`   | `.json`                 |&check;|&check;|
| Python coded binary   | `python` | `.py`                   |&check;|&check;|
| Pascal coded binary   | `pascal` | `.pas`                  |&check;|&check;|
| BASIC coded binary    | `basic`  | `.bas`                  |&check;|&check;|

[A] requires **libarchive**  
[C] requires **acefile**  
[Y] requires **python3-yenc**  
[Z] requires **ncompress**  

_Note that many of these currently require reading the full archive into memory, which may
not be practicable with e.g ISO9660 or WARC files which can hold whole filesystems._


[*] Identifying raw binary files
--------------------------------

This is the most common format used on old platforms, often with the unhelpful suffix `.fnt`. As there is no metadata, it's up to you to specify the character-cell size. The most common, and default, size is 8x8 (CGA and many 8-bit platforms), followed by 8x16 (VGA) and 8x14 (EGA).

- 8x8 raw files are also known as `.f08`, `.ch8`, `.88`, `.chr`, `.udg`, and many others.
- 8x14 raw files are also known as `.f14` or `.814`.
- 8x16 raw files are also known as `.f16`, Warp 9 `.fnt` or Degas Elite `.fnt`
- Genecar `.car` files are 16x16 raw files.
- Harlekin III `.fnt` files are raw binaries with a 4096x8 pixel bitmap strike hosting 512 8x8 glyphs side by side. Extract with `-strike-width=512`.

It is also useful to check the file size. Raw files commonly hold 96 (ASCII excluding controls), 128 (ASCII), 256, or multiples thereof. Common file sizes therefore are:

|       |  8x8  |  8x14 |  8x16 |
|-------|-------|-------|-------|
| **96**|   768 |  1344 |  1536 |
|**128**|  1024 |  1792 |  2048 |
|**256**|  2048 |  3584 |  4096 |
|**512**|  4096 |  7168 |  8192 |


If your unidentified font file has one of these sizes, chances are it is a raw binary file.


[**] TrueType / OpenType embedded bitmaps
-----------------------------------------

`monobit` can extract bitmaps embedded in TrueType and OpenType font files. It
should be kept in mind that these are primarily intended as scalable formats,
and only exceptionally embed bitmaps to improve rendering on low-resolution displays.

_The vast majority of `.ttf`, `.otf`, `.dfont` etc. files do not contain bitmaps at all_.
This is true even for fonts with a pixelised look.
To convert these you first need to _rasterise_ them, which `monobit` does not do.
Some of the other font tools linked below do have rasterising features.

`monobit` can experimentally output OpenType Bitmap (`.otb`) files, a bitmap-only
file format supported by Linux desktops.


Dependencies
------------

Some formats require
- **PIL** (`Pillow`)
- **reportlab**
- **fontTools**
- **libarchive**
- **python3-yenc**
- **ncompress**
- **acefile**

The renderer additionally employs
- **uniseg**
- **python-bidi**
- **arabic-reshaper**

Almost all can be installed through Pip:

    pip install Pillow reportlab fonttools uniseg python-bidi arabic-reshaper libarchive-c ncompress acefile

The package `python3-yenc` is available at https://github.com/oe-mirrors/python3-yenc and through some Linux distributions.
Without these packages, some functionality may not be available.


Copyright and licences
----------------------

`monobit` and the `yaff` specification are copyright 2019--2024 Rob Hagemans and
released under the [MIT licence](https://opensource.org/licenses/MIT).

`monobit` contains code from:  
- [`mkwinfont`](https://www.chiark.greenend.org.uk/~sgtatham/fonts/) copyright 2001 Simon Tatham. All rights reserved.  
- [`dewinfont`](https://www.chiark.greenend.org.uk/~sgtatham/fonts/) copyright 2001,2017 Simon Tatham. All rights reserved.  
- [OS/2 GPI Font Tools](https://github.com/altsan/os2-gpi-font-tools) (C) 2012 Alexander Taylor  
- [FONDU](https://sourceforge.net/projects/fondu/) copyright (C) 2000,2001,2002,2003 by George Williams

Please refer to the notices in the `windows` and `os2` subpackages and `mac/fond.py` module for licences and more information.

The font files in `tests/fonts` are subject to their own
licences, some of which are more restrictive. These are files used for testing
and development and are not included in the packaged distribution. See `tests/fonts/README.md` and notices included with individual files.


Acknowledgements
----------------

`monobit` would not exist without those documenting,
reverse-engineering, implementing and preserving font formats and files:
- [The Internet Archive](https://archive.org)
- [Archive Team](http://fileformats.archiveteam.org/wiki/Fonts)
- [Jason Scott's textfiles.com](http://textfiles.com)
- [John Elliott's homepage](http://www.seasip.info)
- [Simon Tatham's fonts page](https://www.chiark.greenend.org.uk/~sgtatham/fonts/)
- [Aivosto's character set documentation](https://www.aivosto.com/articles/charsets.html)
- [Rebecca Bettencourt's character set documentation](https://www.kreativekorp.com/charset/)
- [Xiphoseer's Signum Document Toolbox](https://sdo.dseiler.eu/)
- [George Williams et al.'s FontForge documentation](https://fontforge.org/docs/index.html)
- [FreeType Glyph Conventions](https://freetype.org/freetype2/docs/glyphs/index.html)
- ... and many others


Other software
--------------

Other bitmap font tools you could use in conjunction with (or instead of) `monobit` include:
- [FontForge](http://fontforge.github.io/en-US/)
- Rebecca Bettencourt's [Bits'n'Picas](https://github.com/kreativekorp/bitsnpicas)
- John Elliott's [PSFTools](http://www.seasip.info/Unix/PSF/)
- Mark Leisher's [`gbdfed`](http://sofia.nmsu.edu/~mleisher/Software/gbdfed/)
- [RECOIL](https://recoil.sourceforge.net/)
- John Zaitseff's [console font utilities](https://www.zap.org.au/projects/console-fonts-utils/)
- George Williams's [Fondu](https://fondu.sourceforge.net)
- VileR's [Fontraption](https://github.com/viler-int10h/Fontraption/)
