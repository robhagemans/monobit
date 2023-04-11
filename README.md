
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


Supported bitmap formats
------------------------

| Format                | Short Name | Typical Extension           | Read  | Write |
|-----------------------|------------|-----------------------------|-------|-------|
| Amiga Font Contents   | `amiga-fc` | `.font`                     | ✔     |       |
| Amiga font            | `amiga`    |                             | ✔     |       |
| BBC soft font         | `bbc`      |                             | ✔     | ✔     |
| X11/Adobe BDF         | `bdf`      | `.bdf`                      | ✔     | ✔     |
| AngelCode BMFont [P]  | `bmfont` | `.fnt` `.xml` `.json` + images | ✔    | ✔     |
| Raw binary            | `raw`      | `.fnt` `.rom` [*]           | ✔     | ✔     |
| Codepage Information  | `cpi`      | `.cpi`                      | ✔     | ✔     |
| Consoleet / vfontas   | `consoleet`| `.txt`                      | ✔     |       |
| Daisy-Dot             | `daisy`    | `.nlq` `.nl2` `.nl3` `.nl4` | ✔     |       |
| Dashen                | `dashen`   | `.pft`                      | ✔     |       |
| DEC DRCS soft font    | `dec`      |                             | ✔     | ✔     |
| DosStart!             | `dosstart` | `.dsf`                      | ✔     |       |
| FZX font              | `fzx`      | `.fzx`                      | ✔     | ✔     |
| Figlet font           | `figlet`   | `.flf`                      | ✔     | ✔     |
| Windows or OS/2 font  | `mzfon`    | `.fon` `.exe` `.dll`        | ✔     | ✔ (16-bit Windows) |
| FONTX2                | `fontx`    | `.fnt`                      | ✔     | ✔     |
| FONTEDIT              | `fontedit` | `.com`                      | ✔     |       |
| Fontraption           | `frapt`    | `.com`                      | ✔     |       |
| Fontraption TSR       | `frapt-tsr`| `.com`                      | ✔     |       |
| Hanzi Bitmap Font     | `hbf`      | `.hbf` + raw binary         | ✔     | ✔     |
| OS/2 GPI resource     | `gpi`      | `.fnt`                      | ✔     |       |
| Atari GDOS / GEM      | `gdos`     | `.fnt` `.gft` `.vga`        | ✔     | ✔     |
| C64 GEOS ConVerT      | `geos`     | `.cvt`                      | ✔     |       |
| HP PCL soft font      | `hppcl`    | `.sft` `.sfp` `.sfl`        | ✔     | ✔     |
| GNU Unifont           | `unifont`  | `.hex`                      | ✔     | ✔     |
| Extended Hex          | `pcbasic`  | `.hex`                      | ✔     | ✔     |
| hexdraw               | `hexdraw`  | `.draw`                     | ✔     | ✔     |
| Bitmap image [P]      | `image`    | `.png` `.gif` `.bmp`        | ✔     | ✔     |
| Apple IIgs font       | `iigs`     | `.fon`                      | ✔     | ✔     |
| Bare codepage         | `kbd`      | `.cp`                       | ✔     | ✔     |
| REXXCOM Font Mania    | `mania`    | `.com`                      | ✔     |       |
| LISA font library     | `lisa`     | `.bin`                      | ✔     |       |
| MacOS font            | `mac`      | `.dfont` `.suit`            | ✔     |       |
| mkwinfon text format  | `mkwinfon` | `.fd`                       | ✔     |       |
| PSF2AMS PSFCOM        | `psfcom`   | `.com`                      | ✔     |       |
| Bare NFNT resource    | `nfnt`     | `.f`                        | ✔     | ✔     |
| Palm OS font (v1/NFNT)| `palm`     | `.pdb`                      | ✔     |       |
| Optiks PCR Font       | `pcr`      | `.pcr`                      | ✔     |       |
| PCPaint, GRASP, ChiWriter | `pcpaint` | `.set` `.fnt`  `.sft` `.pft` `.eft` ... | ✔ |  |
| PDF chart [R]         | `pdf`      | `.pdf`                      |       | ✔     |
| TeX PKFONT            | `pkfont`   | `.pk`                       | ✔     |       |
| The Print Shop        | `printshop`| `.pnf`                      | ✔     |       |
| PC Screen Font        | `psf`      | `.psf` `.psfu`              | ✔     | ✔ (version 2) |
| PSF2AMS PSFCOM        | `psfcom`   | `.com`                      | ✔     |       |
| PSF2TXT               | `psf2txt`  | `.txt`                      | ✔     |       |
| Signum! 2             | `signum`   | `.e24` `.p9` `.p24` `.l30`  | ✔     |       |
| SFNT embedded bitmap  | `sfnt`     | `.otb` `.ttf` `.otf` [F] [**] | ✔   | ✔ (OTB) |
| SFNT collection       | `ttcf`     | `.otc` `.ttc` [F] [**]      | ✔     | ✔ (OTB) |
| vfont                 | `vfont`    |                             | ✔     | ✔     |
| Bare GEOS resource    | `vlir`     |                             | ✔     |       |
| Windows FNT resource  | `win`      | `.fnt`                      | ✔     | ✔     |
| XBIN font section     | `xbin`     | `.xb`                       | ✔     | ✔     |
| monobit yaff          | `yaff`     | `.yaff`                     | ✔     | ✔     |


[P] - requires **PIL**  
[R] - requires **reportlab**  
[F] - requires **fontTools**


[*] Identifying raw binary files
--------------------------------

This is the most common format used on old platforms, often with the unhelpful suffix `.fnt`. As there is no metadata, it's up to you to specify the character-cell size. The most common, and default, size is 8x8 (CGA and many 8-bit platforms), followed by 8x16 (VGA) and 8x14 (EGA).

- 8x8 raw files are also known as `.f08`, `.ch8`, `.64c`, `.chr`, `.udg`, and many others.
- 8x14 raw files are also known as `.f14` or CHET `.814`.
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


Font format features
--------------------

Here is a comparison of what you can and cannot store in selected formats supported by `monobit`.

| Format        | Unicode | Unicode sequences | Encoding | MBCS | Multiple fonts | Cell size | Proportional | Kerning | Colour/antialiasing | Glyph representation
|---------------|---|---|---|---|---|------|---|---|---|--------------
| `yaff`        | ✔ | ✔ | ✔ | ✔ | ✔ | any  | ✔ | ✔ |   | visual text
| `sfnt`        | ✔ | ✔ | ✔ | ✔ | ✔ | any  | ✔ | ✔ | ✔ | binary
| `bmfont`      | ✔ |   | ✔ | ✔ |   | any  | ✔ | ✔ | ✔ | image
| `bdf`         | ✔ |   | ✔ | ✔ |   | any  | ✔ |   |   | hex
| `nfnt`        |   |   | ✔ | ✔ | ✔ | any  | ✔ | ✔ | ✔ | binary
| `win`         |   |   | ✔ | ✔ | ✔ | any  | ✔ |   |   | binary
| `hexdraw`     | ✔ |   |   |   |   | any  | ✔ |   |   | visual text
| `amiga`       |   |   |   |   | ✔ | any  | ✔ |   | ✔ | binary
| `gdos`        |   |   |   |   |   | any  | ✔ |   |   | binary
| `fzx`         |   |   |   |   |   | any  | ✔ |   |   | binary
| `figlet`      | ✔ |   |   |   |   | any  | ✔ |   | ✔ | visual text
| `vfont`       |   |   |   |   |   | any  | ✔ |   |   | binary
| `pcbasic`     | ✔ | ✔ |   |   |   | 8xN  | multi-cell |   |   | hex
| `unifont`     | ✔ |   |   |   |   | 8x16 | multi-cell |   |   | hex
| `hbf`         |   |   | ✔ | ✔ |   | any  |   |   |   | binary
| `psf` (v2)    | ✔ | ✔ |   |   |   | any  |   |   |   | binary
| `psf` (v1)    | ✔ |   |   |   |   | 8xN  |   |   |   | binary
| `fontx`       |   |   |   | ✔ |   | any  |   |   |   | binary
| `cpi`         |   |   | ✔ |   | ✔ | 8xN  |   |   |   | binary
| `dec`         |   |   |   |   |   | >4xN |   |   |   | binary
| `bbc`         |   |   |   |   |   | 8x8  |   |   |   | binary


Wrapper formats
-----------------

`monobit` will recurse and extract font files from a number of common container,
archive, compression and encoding formats:

| Format                | Name     | Typical Extension       | Read  | Write |
|-----------------------|----------|-------------------------|-------|-------|
| PKZip/WinZip          | `zip`    | `.zip`                  | ✔     | ✔     |
| GNU tar               | `tar`    | `.tar` `.tgz`           | ✔     | ✔     |
| GZip                  | `gzip`   | `.gz`                   | ✔     | ✔     |
| BZip2                 | `bzip2`  | `.bz2`                  | ✔     | ✔     |
| XZ/LZMA               | `lzma`   | `.xz` `.lzma`           | ✔     | ✔     |
| AppleSingle           | `apple1` | `.as`                   | ✔     |       |
| AppleDouble           | `apple2` | `.adf` `.rsrc`          | ✔     |       |
| MacBinary             | `macbin` | `.bin`                  | ✔     |       |
| BinHex 4.0            | `binhex` | `.hqx`                  | ✔     |       |
| C or C++ coded binary | `c`      | `.c` `.cpp` `.cc` `.h`  | ✔     | ✔     |
| JSON coded binary     | `json`   | `.json`                 | ✔     | ✔     |
| Python coded binary   | `python` | `.py`                   | ✔     | ✔     |
| Pascal coded binary   | `pascal` | `.pas`                  | ✔     |       |
| BASIC coded binary    | `basic`  | `.bas`                  | ✔     | ✔     |


Stroke formats
--------------

Stroke font support is experimental. Stroke fonts are scalable fonts defined as
line segments. They are fundamentally different from modern fonts in that they
define single strokes whereas modern fonts define outlines to be filled with ink.
Additionally, the fonts currently supported consist of straight line segments only.


| Format                     | Short Name | Typical Extension | Read  | Write |
|----------------------------|------------|-------------------|-------|-------|
| monobit yaff               | `yaff`     | `.yaff`           | ✔     | ✔     |
| SVG Fonts                  | `svg`      | `.svg`            | ✔     | ✔     |
| Windows resource           | `win`      | `.fnt`            | ✔     | ✔     |
| Windows font               | `fon`      | `.fon`            | ✔    | ✔ (NE) |
| Borland Graphics Interface | `borland`  | `.chr`            | ✔     | ✔     |
| Hershey fonts (Jim Hurt)   | `hurt`     | `.jhf`            | ✔     |       |
| DOSStart                   | `dosstart` | `.dsf`            | ✔     |       |


Dependencies
------------

Some formats require
- **PIL** (`Pillow`)
- **reportlab**
- **fontTools**

The renderer additionally employs
- **uniseg**
- **python-bidi**
- **arabic-reshaper**

All can be installed through Pip:

    pip install Pillow reportlab fonttools uniseg python-bidi arabic-reshaper

Without these packages, some functionality may not be available.


Copyright and licences
----------------------

`monobit` and the `yaff` specification are copyright 2019--2023 Rob Hagemans and
released under the [MIT licence](https://opensource.org/licenses/MIT).

`monobit` contains code from:  
- [`mkwinfont`](https://www.chiark.greenend.org.uk/~sgtatham/fonts/) copyright 2001 Simon Tatham. All rights reserved.  
- [`dewinfont`](https://www.chiark.greenend.org.uk/~sgtatham/fonts/) copyright 2001,2017 Simon Tatham. All rights reserved.  
- [OS/2 GPI Font Tools](https://github.com/altsan/os2-gpi-font-tools) (C) 2012 Alexander Taylor  

Please refer to the notices in the `windows` and `os2` subpackages for licences and more information.

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
- [Simon Tatham's fonts page](https://www.chiark.greenend.org.uk/~sgtatham/fonts/):
- [Aivosto's character set documentation](https://www.aivosto.com/articles/charsets.html)
- [Rebecca Bettencourt's character set documentation](https://www.kreativekorp.com/charset/)
- [Xiphoseer's Signum Document Toolbox](https://sdo.dseiler.eu/)
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
