
Tools for working with monochrome bitmap fonts
==============================================

The `monobit` tools let you modify bitmap fonts and convert between several formats.

`monobit`'s native format is `yaff`, a human-friendly, text-based visual format similar to the ones used by
Roman Czyborra's `hexdraw`, Simon Tatham's `mkwinfont` and John Elliott's `psftools`. A specification
of the font format follows below.

A a working Python 3 installation is required and some formats or features require additional packages to be installed; see _Dependencies_ below.

`monobit` can be used as a Python package or as a command-line tool.


Usage examples
--------------

##### Convert utility

Here are some examples of how to use the conversion utility.

`python3 convert.py -h`

Display usage summary and command-line options

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

For example:

    me@bandit:~$ python3 banner.py monobit. --font=VGASYS.FON --scale=2x1
    --------------------------------------------------------------------------@@@@------------@@@@------------------
    --------------------------------------------------------------------------@@@@------------@@@@----@@@@----------
    --------------------------------------------------------------------------@@@@--------------------@@@@----------
    --@@@@@@@@@@@@@@@@@@--------@@@@@@@@------@@@@@@@@@@--------@@@@@@@@------@@@@@@@@@@------@@@@--@@@@@@@@--------
    --@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----------
    --@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----------
    --@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----------
    --@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----------
    --@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@----@@@@--
    --@@@@----@@@@----@@@@------@@@@@@@@------@@@@----@@@@------@@@@@@@@------@@@@@@@@@@------@@@@------@@@@--@@@@--
    ----------------------------------------------------------------------------------------------------------------
    ----------------------------------------------------------------------------------------------------------------
    ----------------------------------------------------------------------------------------------------------------
    ----------------------------------------------------------------------------------------------------------------
    ----------------------------------------------------------------------------------------------------------------
    ----------------------------------------------------------------------------------------------------------------

or:

    me@bandit:~$ python3 banner.py monobit. --font=VGASYS.FON --rotate=1 --ink='#' --paper=' '

          #######   
          #######   
                #   
                #   
          #######   
          #######   
                #   
                #   
          #######   
          ######    


           #####    
          #######   
          #     #   
          #     #   
          #######   
           #####    


          #######   
          #######   
                #   
                #   
          #######   
          ######    


           #####    
          #######   
          #     #   
          #     #   
          #######   
           #####    


          ##########
          ##########
          #     #   
          #     #   
          #######   
           #####    


          ####### ##
          ####### ##

                #   
           ########
          #########
          #     #   

          ##        
          ##        




Supported formats
-----------------

| Format                | Version  | Typical Extension           | Native OS   | Read  | Write |
|-----------------------|----------|-----------------------------|-------------|-------|-------|
| monobit yaff          |          | `.yaff`                     |             | ✔     | ✔     |
| hexdraw               |          | `.draw`                     |             | ✔     | ✔     |
| GNU Unifont           |          | `.hex`                      |             | ✔     | ✔     |
| PC Screen Font        | 1        | `.psf`                      | MS-DOS      | ✔     |       |
| PC Screen Font        | 2        | `.psf` `.psfu`              | Linux       | ✔     | ✔     |
| Raw binary            |          | `.fnt` `.rom` `.f??` `.ch8` `.64c` |      | ✔     | ✔     |
| Bitmap image          |          | `.png` `.gif` `.bmp`        |             | ✔ (P) | ✔ (P) |
| PDF chart             |          | `.pdf`                      |             |       | ✔ (R) |
| C or C++ source code  |          | `.c` `.cpp` `.cc` `.h`      |             | ✔     | ✔     |
| JavaScript source code|          | `.js` `.json`               |             | ✔     |       |
| Python source code    |          | `.py`                       |             | ✔     |       |
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
| FZX Font              |          | `.fzx`                      | ZX Spectrum | ✔     |       |
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


The `yaff` format
=================

Design aims
-----------

The `yaff` format has the following design aims:
- **Human-friendly.** Truly human-readable and human-editable. For example, BDF and XML claim to be
  human-readable formats, but let's not kid ourselves. Human-friendly means plain text, flat,
  immediately visualised, easy on the eye, and light and obvious syntax.
  We should avoid duplication of information, unless it is of obvious use to a human user.
- **Able to represent fixed-width and proportional fonts.**
- **Preserves comments, metadata and metrics.** Formats such as BDF contain a wealth of metadata such as
  names, acknowledgements and style specification, but also font metrics that affect the way the font is displayed. The
  `yaff` format should preserve these.
- **Able to represent Unicode fonts as well as codepage fonts.**

Non-aims include:
- Colour/greyscale fonts and anti-aliasing. It has to stop somewhere.
- Performance. Bitmap fonts are small; computers are fast and have tons of memory.


Example
-------

In the spirit of human-friendliness, a short example is probably more informative than the full specification.

    # This is a global comment
    # spanning multiple lines.

    name: Test Roman 8px
    family: Test
    notice:
        Test is the property of T€$ţ0Яζ Inc.
        It's not a very useful font.
    encoding: totally-made-up

    # The letter A is the first letter of the Latin alphabet.
    # We've got three kinds of labels: unicode, codepage, and text.
    u+0041:
    0x41:
    latin_a:
        ....
        .@..
        @.@.
        @@@.
        @.@.
        @.@.

    # Each type of label is optional.
    # We're only going to give a unicode code point for B.
    u+0042:
        .....
        @@@..
        @..@.
        @@@..
        @..@.
        @@@..

    # Or for example just a text label.
    # This is a 0x0 empty glyph, by the way.
    empty:
        -

    # Multiple labels of the same type are OK. Numbers may be decimal, too.
    # Glyphs don't need to be the same width or height
    0x01:
    0x02:
    255:
    smiley:
        ......
        .@..@.
        ......
        .@..@.
        ..@@..

    # Multiple code points may define a grapheme cluster
    u+0061, u+0300:
    small_a_grave:
        @...
        .@..
        ....
        .@@.
        @.@.
        @.@.
        .@@@





Specification
-------------

#### Encoding

`yaff` files must be text files encoded as UTF-8.
- A byte-order mark (`u+FEFF`) may be included at the start of the file.
- Lines must be terminated by one of the following line endings:
  `LF` (`u+000a`), `CR LF` (`u+000d u+000a`), or `CR` (`u+000d`).
- *Whitespace* consists of spaces (`u+0020`) and tabs (`u+0009`).
- `yaff` files must not include:
  * Control characters (Unicode category Cc) other than whitespace and line endings as defined above,
  * The line separators `u+2028` and `u+2029`, or
  * Any of the 66 Unicode *noncharacters*.

#### Components
`yaff` files consist of *glyph definitions*, *properties* and *comments*.
Each of these components is optional; an empty file is a valid (if pointless) `yaff` file.

#### Comments
A line starting with a hash `#` contains a *comment* only.
* `#` must be the first character of the line; inline comments are not allowed.
* If the first character after `#` is whitespace, it does not form part of the comment.
* Further whitespace characters do form part of the comment.
* The line ending does not form part of the comment.
* The comment may contain any character that is allowed in a `yaff` file.

#### Properties
A *property* can span multiple lines. It starts with a *key* followed by the separator `:`, and a *value*.

A *key* consists only of ASCII letters, ASCII digits, the underscore `_`, the dash `-`, or the full stop `.`.
* The key is not case sensitive.
* In a key, the `-` and the `_` are considered equivalent.
* The key must be given at the start of the line. Leading whitepace is not allowed.
* The key and the separator `:` must be on the same line.

Whitespace between the key, the separator, and the value is allowed.
There may be at most one newline between the separator and the value.
* If there is no newline between the separator and the value, the value consists of the remainder
  of the line following the separator, excluding leading and trailing whitespace and the line ending.
* If there is a newline following the separator, the value consists of all following lines which start
  with whitespace. There must be at least one such line. Leading and trailing whitespace on these
  lines does not form part of the value, but the newlines do.
* A value may contain any character that is allowed in a `yaff` file.
* A value must not consist solely of `.`, `@`, and whitespace characters.
* A value must not consist of a single `-`.
* A value must not be empty.
* If a value starts and ends with a double quote, these quotes are stripped and everything in between is used unchanged.

#### Glyph definitions
A *glyph definition* consists of one or more *labels*, followed by a *glyph*. If there are multiple
labels, all are considered to point to the glyph that follows.

##### Labels
A *label* must be followed by a separator `:`, optional whitespace, and a line ending.
* The label must be given at the start of the line. Leading whitespace is not allowed.
* A label must start with an ascii letter or digit, an underscore `_`, a dash `-`, a dot `.`, or a double quote `"`.
* If a label starts and ends with a double quote, these quotes are stripped and everything in between is used unchanged.
* A label has one of three types: *character*, *codepoint*, or *tag*.

If a label starts with a digit, it is a *codepoint*.
* A codepoint label may consist of multiple elements, separated by commas and optional whitespace.
* Each element represents an integer value.
* If all characters in the element are digits, the element is in decimal format. Leading `0`s are allowed.
* If the first two characters are `0x` or `0X`, the element is hexadecimal. All further characters
  must be hex digits and are not case sensitive.
* If the first two characters are `0o` or `0O`, the element is octal. All further characters must
  be octal digits.
* If a codepoint label consists of multiple elements, they represent a multi-byte codepoint sequence
pointing to a single glyph.

If a label starts with `u+` or `U+`, it is a Unicode *character*.
  * A character label may consist of multiple elements, separated by commas and optional whitespace.
  * Each element must start with `u+` or `U+`. All further characters must be hex digits and are not case sensitive.
  * Each element represents a Unicode point in hexadecimal notation. Together they
  are taken to represent a single grapheme cluster.

If a label does not start with a digit, `u+` or `U+`, it is a *tag*.
  * Tags are case-sensitive and may contain any kind of character.

##### Glyphs

A *glyph* may span multiple lines.
* The lines of a glyph must start with whitespace. Trailing whitespace is allowed.
* If a glyph consists of the character `-` only, it is the empty glyph.
* Otherwise, the glyph must consist of the characters `.` and `@` only.
* After removal of whitespace, all lines in the glyph must be of equal length.
* A `@` represents an inked pixel in the glyph, a `.` represents an un-inked pixel.


Recognised properties
---------------------

The following are font properties `monobit` is aware of. Other properties may be defined as and when needed.

##### Metrics

_Metrics_ are properties that affect how the font is rendered.
They are:
- `direction`: Direction of writing. At present, only `left-to-right` is supported.
- `offset` (_x_ _y_ pair): The shift from the _glyph origin_ to the _raster origin_.
- `tracking`: Spacing following the glyph raster (i.e. to the right in a left-to-right font).
- `leading`: Spacing between lines of text rasters (i.e. vertical spacing in a horizontal font).
- `kerning`: Adjustment to tracking for specific glyph pairs. E.g. the pair `AV` may have negative
kerning, so that they are displayed tighter than they otherwise would.

##### Characteristics

_Characteristics_ are descriptive in nature. They can be specified or calculated. Usually specified are:
- `x-height`: height of a lowercase `x` relative to the baseline.
- `cap-height`: height of a capital letter relative to the baseline.
- `ascent`: height of lowercase letters such as `f` that extend above the x-height.
- `descent`: extent of lowercase letters such as `j` below the baseline.
- `pixel-size`: pixel size (equals ascent plus descent).

Characteristics inferred from the glyphs are:
- `raster`: largest raster needed to define a glyph; coordinates (left, bottom, right, top)
- `ink-bounds`: smallest box that encompasses all ink if all glyphs are overlayed at the same origin.
                coordinates (left, bottom, right, top)
- `raster-size`: (width, height) of raster.
- `bounding-box`: (width, height) of ink-bounds.
- `average-advance`: average advance width across glyphs.
- `max-advance`: maximum advance width across glyphs.
- `cap-advance`: advance width of capital letter `X`.
- `spacing`: type of font, can be one of:
  - `proportional`: glyphs have different advance widths, e.g. `M` is wider than `i`.
  - `monospace`: all glyphs have the same advance width.
  - `character-cell`: all glyphs can be defined on a raster of fixed size and displayed without overlap.
  - `multi-cell`: like `character-cell`, but some glyphs may take up multiple cells.

Characteristics that give a font's identity are:
- `family`: typeface or font family name
- `point-size`: nominal size of the font in points
- `name`: full name of the font
- `revision`: version

Font description characteristics that can be used to compare different fonts in a family:
- `style`: e.g. `serif`, `sans`, ...
- `weight`: e.g. `bold`, `normal`, `light`, ...
- `slant`: e.g. `roman`, `italic`, `oblique`, ...
- `setwidth`: e.g. `expanded`, `normal`, `condensed`, ...
- `decoration`: e.g. `strikethrough`, `underline`, ...

##### Metadata

_Metadata_ are circumstantial properties. They can be related to authorship:
- `foundry`: author or publisher of the font
- `copyright`: copyright information
- `notice`: licensing information

They can be related to the target system:
- `device`: target device, e.g. `EGA`, `VGA`, `printer`
- `pixel-aspect`: target aspect ratio of pixels, X:Y
- `dpi`: target resolution in dots per inch

Or they can be related to processing:
- `converter`: software used to produce the present file, e.g. `monobit`.
- `source-name`: file name from which the font was originally extracted.
- `source-format`: file format from which the font was originally extracted.
- `history`: summary of processing steps applied since extraction.




##### Illustration of key properties

The below figure illustrates the typographic properties. Note that the font shown has negative offsets, so that a glyph's inked pixels may partially overlap the tracking space and even the raster of the preceding glyph.


                    ┬       ┌─┬─┬─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐
                    │       │ │ │ │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │ │   │ │ │ │   ascent = 5
                ┬           ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤   ┬
                |   │       │ │ │ │ │ │ │   │ │ │ │   │ │█│ │   │ │█│█│   │ │ │█│   │ │ │ │   │  cap-height = 4
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤      ┬
                |   │       │ │ │ │ │█│ │   │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │█│   │  │  x─height = 3
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤         ┬
                |   │       │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│█│ │   │ │ │█│   │ │█│ │   │  │  │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
                |   │       │ │ │ │█│█│█│   │ │█│ │   │█│ │█│   │█│ │ │   │ │ │█│   │█│ │ │   │  │  │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
                |   │       │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│ │ │   │ │ │█│  ▓│ │ │ │   │  │  │
                            ├─┼─┼─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤   ┴  ┴  ┴  ┬
                |   │       │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │█│█│ │▓  │ │ │ │            │
                ┴           ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤            ┴
    pixel-size = 6  │       │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▓│   │ │ │ │            descent = 1
                    ┴   ┬   X─┴─┴─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘
    raster-height = 8   │
                        ┴   ┌─┬─┬─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐ . . top-line
              leading = 1   │ │ │ │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │ │   │ │ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . ascent-line
                            │ │ │ │ │ │ │   │ │ │ │   │ │█│ │   │ │█│█│   │ │ │█│   │ │ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . cap-line
                            │ │ │ │ │█│ │   │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │█│
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . mean-line
                            │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│█│ │   │ │ │█│   │ │█│ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
                            │ │ │ │█│█│█│   │ │█│ │   │█│ │█│   │█│ │ │   │ │ │█│   │█│ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
                            │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│ │ │   │ │ │█│  ▓│ │ │ │
          offset.y = -2 O   ├─┼─┼─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤ . . baseline
                        │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │█│█│ │▓  │ │ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . descent-line
                        │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▓│   │ │ │ │
                        X   X─┴─┴─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘ . . bottom-line

                            X─ ─ ─O offset.x = -3

           raster-width = 6 ├─ ─ ─ ─ ─ ─┤
                                  O─ ─ ─ ─ ─O advance-width = 5
                                        ├─ ─O tracking = 2


                            O = glyph-origin
                            X = raster-origin



What does `yaff` stand for?
---------------------------
"Yaff" is a sound made by small dogs in Scotland.


Does the world need yet another font format?
--------------------------------------------
No. No, it doesn't. I did, though. Representing a font bitmap in text is far from a new idea and
there are tons of programs that do something similar. However, in most cases these formats either lacked
the flexibility to represent proportional fonts, could not preserve metadata, required too much
repetitive specifications or included annoying syntactic frippery. That said, text fonts have been
implemented independently so many times by so many people that I may have missed out a format that
I could have used instead of rolling my own. Ah, well.

Is this a dialect of YAML?
--------------------------
No. Obviously, the `yaff` format closely resembles YAML and was inspired by it.
Somewhat unfortunately, it is not valid YAML, though. This is due to multiple labels - I haven't found a way
to make it valid YAML without introducing ugly and contrived syntax that would harm the human-friendliness.
