
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
Roman Czyborra's `hexdraw`, Simon Tatham's `mkwinfont` and John Elliott's `psftools`. A specification
of the font format is given in [this repository](YAFF.md).

A a working Python 3 installation is required and some formats or features require additional packages to be installed; see _Dependencies_ below.

`monobit` can be used as a Python package or as a command-line tool.


Usage examples
--------------

##### Convert utility

Here are some examples of how to use the conversion utility.

`python3 convert.py -h`

Display usage summary and command-line options

`python3 convert.py --from=raw -h`

Display usage summary and additional format-specific command-line options for conversion from raw binary.
Format-specific options for loading and saving are *only* available when specifying
the `--from` or `--to` arguments, respectively.

`python3 convert.py fixedsys.fon`

Recognise the source file format from "magic bytes" or suffix (here, a Windows font) and write fonts
to standard output in `yaff` format.

`python3 convert.py roman.bdf --to=hex`

Read font in BDF format and  write to standard output as Unifont HEX.

`python3 convert.py fixed.psf fixed.png`

Read font in PSF format and write to disk as image in PNG format.

`python3 convert.py --from=c --to=bdf`

Read font from standard input as C-source and write to standard output as BDF.

The converter transparently reads and writes `gz`, `bz2`, or `xz`-compressed font files and can read
and write `zip` and `tar` archives. Some font formats contain multiple fonts whereas others can contain only one; the converter will write multiple files to a directory or archive if needed.

##### Modify utility

The modify utility reads a font file, performs an operation on it and writes it out.
Check `python3 modify.py -h` for usage.

##### Banner utility

The banner utility renders text to standard output in a given font. This is similar to the ancient
`banner` commands included in GNU and BSD Unixes.

For example, the banner at the top of this `README` was made with

    me@bandit:~$ python3 banner.py '| monobit. |' --font=VGASYS.FON

`banner.py` has anumer of rendering options - you can choose fonts, change the "ink" and "paper" 
characters, set a margin, scale text, and rotate by quarter turns. 
Check `python3 banner.py -h` for usage.


Supported formats
-----------------

| Format                | Version  | Typical Extension           | Native OS   | Read  | Write |
|-----------------------|----------|-----------------------------|-------------|-------|-------|
| monobit yaff          |          | `.yaff`                     |             | ✔     | ✔     |
| hexdraw               |          | `.draw`                     |             | ✔     | ✔     |
| GNU Unifont           |          | `.hex`                      |             | ✔     | ✔     |
| PC Screen Font        | 1        | `.psf`                      | MS-DOS      | ✔     |       |
| PC Screen Font        | 2        | `.psf` `.psfu`              | Linux       | ✔     | ✔     |
| Raw binary            |          | `.fnt` `.rom` `.f??` `.ch8` `.64c` `.chr`|| ✔     | ✔     |
| Bitmap image          |          | `.png` `.gif` `.bmp`        |             | ✔ (P) | ✔ (P) |
| PDF chart             |          | `.pdf`                      |             |       | ✔ (R) |
| C or C++ source code  |          | `.c` `.cpp` `.cc` `.h`      |             | ✔     | ✔     |
| JavaScript source code|          | `.js` `.json`               |             | ✔     | ✔     |
| Python source code    |          | `.py`                       |             | ✔     | ✔     |
| AngelCode BMFont      | Text     | `.fnt` + images             |             | ✔ (P) | ✔ (P) |
| AngelCode BMFont      | Binary   | `.fnt` + images             |             | ✔ (P) |       |
| AngelCode BMFont      | XML      | `.fnt` `.xml` + images      |             | ✔ (P) |       |
| AngelCode BMFont      | JSON     | `.json` + images            |             | ✔ (P) | ✔ (P) |
| X11/Adobe BDF         |          | `.bdf`                      | Unix        | ✔     | ✔     |
| Codepage Information  | FONT     | `.cpi`                      | MS-DOS      | ✔     |       |
| Codepage Information  | FONT.NT  | `.cpi`                      | Windows NT  | ✔     |       |
| Codepage Information  | DRFONT   | `.cpi`                      | DR-DOS      | ✔     |       |
| `kbd` Codepage        |          | `.cp`                       | Linux       | ✔     |       |
| Amiga Font Contents   |          | `.font`                     | Amiga OS    | ✔     |       |
| Amiga Font            |          |                             | Amiga OS    | ✔     |       |
| FZX Font              |          | `.fzx`                      | ZX Spectrum | ✔     | ✔     |
| Figlet                |          | `.flf`                      | Unix        | ✔     | ✔     |
| MacOS font            | FONT     |                             | MacOS       | ✔     |       |
| MacOS font            | NFNT/FOND|                             | MacOS       | ✔     |       |
| Windows resource      | 1.0      | `.fnt`                      | Windows 1.x | ✔     |       |
| Windows resource      | 2.0      | `.fnt`                      | Windows 2.x | ✔     | ✔     |
| Windows resource      | 3.0      | `.fnt`                      | Windows 3.x | ✔     | ✔     |
| Windows font          | 1.0 NE   | `.fon`                      | Windows 1.x | ✔     |       |
| Windows font          | 2.0 NE   | `.fon`                      | Windows 2.x | ✔     | ✔     |
| Windows font          | 3.0 NE   | `.fon`                      | Windows 3.x | ✔     | ✔     |
| Windows font          | 2.0 PE   | `.fon`                      | Windows 2.x | ✔     |       |
| Windows font          | 3.0 PE   | `.fon`                      | Windows 3.x | ✔     |       |  


Font format features
--------------------

Here is a comparison of what you can and cannot store in selected formats supported by `monobit`.

| Format        | Unicode | Unicode sequences | Encoding | MBCS | Multiple fonts | Cell size | Proportional | Kerning | Colour/antialiasing | Glyph representation
|---------------|---|---|---|---|---|------|---|---|---|--------------
| `yaff`        | ✔ | ✔ | ✔ | ✔ | ✔ | any  | ✔ | ✔ |   | visual text
| `bmfont`      | ✔ |   | ✔ | ✔ |   | any  | ✔ | ✔ | ✔ | image
| `bdf`         | ✔ |   | ✔ | ✔ |   | any  | ✔ |   |   | hex
| `mac-*`       |   |   | ✔ | ✔ | ✔ | any  | ✔ | ✔ | ✔ | binary
| `win-*`       |   |   | ✔ | ✔ | ✔ | any  | ✔ |   |   | binary
| `hexdraw`     | ✔ |   |   |   |   | any  | ✔ |   |   | visual text
| `amiga-*`     |   |   |   |   | ✔ | any  | ✔ |   | ✔ | binary
| `fzx`         |   |   |   |   |   | any  | ✔ |   |   | binary
| `hext`        | ✔ | ✔ |   |   |   | 8xN  | multi-cell |   |   | hex
| `hex`         | ✔ |   |   |   |   | 8x16 | multi-cell |   |   | hex
| `psf.2`       | ✔ | ✔ |   |   |   | any  |   |   |   | binary
| `psf.1`       | ✔ |   |   |   |   | 8xN  |   |   |   | binary
| `cpi`         |   |   | ✔ |   | ✔ | 8xN  |   |   |   | binary


Dependencies
------------

(P) - requires **PIL**, install with `pip3 install Pillow`.  
(R) - requires **reportlab**, install with `pip3 install reportlab`.  


Licence
-------

`monobit` and the `yaff` specification are released under the
[Expat MIT licence](https://opensource.org/licenses/MIT).


Acknowledgements
----------------

`monobit` contains code from Simon Tatham's `mkwinfont` and `dewinfont`.


Other software
--------------

Other bitmap font tools you could use in conjunction with (or instead of) `monobit` include:
- [FontForge](http://fontforge.github.io/en-US/)
- Rebecca Bettencourt's [Bits'n'Picas](https://github.com/kreativekorp/bitsnpicas)
- John Elliott's [PSFTools](http://www.seasip.info/Unix/PSF/)
- Mark Leisher's [`gbdfed`](http://sofia.nmsu.edu/~mleisher/Software/gbdfed/)
- Simon Tatham's [`mkwinfont`/`dewinfont`](https://www.chiark.greenend.org.uk/~sgtatham/fonts/)


