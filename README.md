
Tools for working with monochrome bitmap fonts
==============================================

The `monobit` tools let you modify bitmap fonts and convert between several formats.

`monobit`'s native format is `yaff`, a human-friendly, text-based visual format similar to the ones used by
Roman Czyborra's `hexdraw`, Simon Tatham's `mkwinfont` and John Elliott's `psftools`. A specification
of the font format follows below.

Supported formats
-----------------

| Format                | Version  | Typical Extension           | Native OS   | Read  | Write |
|-----------------------|----------|-----------------------------|-------------|-------|-------|
| monobit yaff          |          | `.yaff`                     |             | ✔     | ✔     |
| hexdraw               |          | `.draw`                     |             | ✔     | ✔     |
| GNU Unifont           |          | `.hex`                      |             | ✔     | ✔     |
| PC Screen Font        | 1        | `.psf`                      | Linux       | ✔     |       |
| PC Screen Font        | 2        | `.psf`                      | Linux       | ✔     | ✔     |
| Raw binary            |          | `.fnt` `.rom` `.f??` `.ch8` |             | ✔     | ✔     |
| Bitmap image          |          | `.png` `.gif` `.bmp`        |             | ✔     | ✔     |
| C or C++ source code  |          | `.c` `.cpp` `.h`            |             | ✔     |       |
| AngelCode BMFont      | Text     | `.fnt` + images             |             | ✔     | ✔     |
| AngelCode BMFont      | Binary   | `.fnt` + images             |             | ✔     |       |
| AngelCode BMFont      | XML      | `.fnt` `.xml` + images      |             | ✔     |       |
| AngelCode BMFont      | JSON     | `.json` + images            |             | ✔     |       |
| X11/Adobe BDF         |          | `.bdf`                      | Unix        | ✔     | ✔     |
| Codepage Information  | FONT     | `.cpi`                      | MS-DOS      | ✔     |       |
| Codepage Information  | FONT.NT  | `.cpi`                      | Windows NT  | ✔     |       |
| Codepage Information  | DRFONT   | `.cpi`                      | DR-DOS      | ✔     |       |
| `kbd` Codepage        |          | `.cp`                       | Linux       | ✔     |       |
| Amiga Font            |          |                             | Amiga OS    | ✔     |       |
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


Roadmap
-------

**Warning**: `monobit` is currently in alpha stage and most likely broken at any point in time.

Work is underway to add:
- PCF
- OS/2, GEM, Atari, C64, GEOS, and ZX Spectrum font files
- testing
- a simple REPL interface for manipulating fonts


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

#### Glyph definitions
A *glyph definition* consists of one or more *labels*, followed by a *glyph*. If there are multple labels,
all are considered to point to the glyph that follows.

A *label* consists of one or more *label elements* separated by commas ','.
The label must be followed by a separator `:` and a line ending.
* The label is not case sensitive.
* The label must be given at the start of the line. Leading whitepace is not allowed.
* Whitespace between the label elements, commas, the separator, and the line ending is allowed.

A *label element* consists only of ASCII letters, ASCII digits, the underscore `_` the dash `-`, and the plus `+`.
* A label element has one of three types: *Unicode code point*, *ordinal*, or *text label*.
* If a label element starts with a digit, it is an *ordinal*.
  * If all characters are digits, the ordinal is in decimal format.
  * If the first two characters are `0x`, the ordinal is hexadecimal. All further characters must
    be case-insensitive hex digits.
  * If the first two characters are `0o`, the ordinal is octal. All further characters must be octal digits.
* If a label element contains a `+`, it is a *Unicode code point*.
  * Its first two characters must be `u+` or `U+`. All further characters must
    be case-insensitive hex digits.
  * The label represents a Unicode code point in hexadecimal notation.
* If a label element starts with an ASCII letter, `-` or `_` and does not contain `+`, it is a *text label*.
  * In a text label, the `-` and the `_` are considered equivalent.
  * Text labels are not case sensitive.
* If a label element does not fit in any of the above three categories, then it is not a valid label element.

If a label consists of more than one label element, they must be of the same type and must not be text labels.
* If they are Unicode code points, together they represent a single grapheme cluster.
* If they are ordinals, together they represent a single multibyte code page sequence.

A *glyph* may span multiple lines.
* The lines of a glyph must start with whitespace. Trailing whitespace is allowed.
* If a glyph consists of the character `-` only, it is the empty glyph.
* Otherwise, the glyph must consist of the characters `.` and `@` only.
* After removal of whitespace, all lines in the glyph must be of equal length.
* A `@` represents an inked pixel in the glyph, a `.` represents an un-inked pixel.


### Metrics

The key properties defining font metrics are:
- `offset` (_x_ _y_ pair): The shift from the _glyph origin_ to the _raster origin_.
- `tracking`: Spacing following the glyph raster (i.e. to the right in a left-to-right font).
- `leading`: Spacing between lines of text rasters (i.e. vertical spacing in a horizontal font).

The below figure illustrates these. Note that the font shown has negative offsets, so that a glyph's
inked pixels may partially overlap the tracking space and even the raster of the preceding glyph. 


                        ┌─┬─┬─┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐
                        │ │ │ │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │ │   │ │ │ │  ascent = 5
                        ├─┼─┼─┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤  ┬
                        │ │ │ │ │ │ │   │ │ │ │   │ │█│ │   │ │█│█│   │ │ │█│   │ │ │ │  │ cap-height = 4
                        ├─┼─┼─┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤    ┬
                        │ │ │ │ │█│ │   │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │█│  │ │ x─height = 3
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤      ┬
                        │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│█│ │   │ │ │█│   │ │█│ │  │ │ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤
                        │ │ │ │█│█│█│   │ │█│ │   │█│ │█│   │█│ │ │   │ │ │█│   │█│ │ │  │ │ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤
                        │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│ │ │   │ │ │█│  ▒│ │ │ │  │ │ │
                  ┬     ├─┼─┼─O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤  ┴ ┴ ┴
                  │     │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │█│█│ │▒  │ │ │ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤
                  │     │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▒│   │ │ │ │
      descent = 2 ┴ ┬   X─┴─┴─┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘
                    │
                    ┴   ┌─┬─┬─┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐   ┬─┬─┬─┐ . . top-line
          leading = 1   │ │ │ │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │ │   │ │ │ │
                        ├─┼─┼─┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . . ascent-line
                        │ │ │ │ │ │ │   │ │ │ │   │ │█│ │   │ │█│█│   │ │ │█│   │ │ │ │
                        ├─┼─┼─┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . ┼─┼─┼─┤ . . cap-line
                        │ │ │ │ │█│ │   │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │█│
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤ . . mean-line
                        │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│█│ │   │ │ │█│   │ │█│ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤
                        │ │ │ │█│█│█│   │ │█│ │   │█│ │█│   │█│ │ │   │ │ │█│   │█│ │ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤
                        │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│ │ │   │ │ │█│  ▒│ │ │ │
      offset.y = -2 ┬   ├─┼─┼─O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . O─┼─┼─┤ . . baseline
                    │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │█│█│ │▒  │ │ │ │
                        ├─┼─┼─┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤   ┼─┼─┼─┤ . . descent-line
                    │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▒│   │ │ │ │
                    v   X─┴─┴─┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘   ┴─┴─┴─┘ . . bottom-line

                        <─ ─ ─┤ offset.x = -3


                              O─ ─ ─ ─ ─O advance-width = 5
                                    ├─ ─┤ tracking = 2

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
