
    .@@.......................@@..@@.....@@.
    .@@......................@@..@@......@@.
    .@@......................@@..@@......@@.
    .@@.....@@....@@..@@@@..@@@@@@@@.....@@.
    .@@.....@@....@@.@@..@@..@@..@@......@@.
    .@@......@@..@@....@@@@..@@..@@......@@.
    .@@......@@..@@...@@.@@..@@..@@......@@.
    .@@.......@@@@...@@..@@..@@..@@......@@.
    .@@.......@@@@...@@..@@..@@..@@......@@.
    .@@........@@.....@@@@@..@@..@@......@@.
    .@@........@@........................@@.
    .@@.......@@.........................@@.
    .@@......@@..........................@@.


The `yaff` font file format
===========================

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

    # the file starts with global properties

    name: Test Roman 8px
    family: Test
    notice:
        Test is the property of T€$ţ0Яζ Inc.
        It's not a very useful font.
    encoding: totally-made-up

    # glyph definitions follow after the global properties section

    # The letter A is the first letter of the Latin alphabet.
    # We've got three kinds of labels: unicode character, codepage, and tag.
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


    # Or for example, just a tag.
    # A glyph may contain per-glyph metrics
    latin_c:
        ....
        .@@.
        @..@
        @...
        @..@
        .@@.

        tracking: 1


    # This is a special notation for a 0x0 empty glyph, with the tag "empty".
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


    # Single quotes ensure a label is interpreted as a unicode character sequence
    # this is equivalent to u+0066, u+0066
    'ff':
        ..@@@
        .@.@.
        .@.@.
        @@@@@
        .@.@.
        .@.@.
        .@.@.

    # While double quotes ensure a label is interpreted as a tag
    "my_à":
        @...
        .@..
        ....
        .@@.
        @.@.
        @.@.
        .@@@

    # It's possible, though not recommended, to define a glyph with no labels at all
    # the colon is still required as a separator
    :
        ......
        .@..@.
        ......
        .@..@.
        ..@@..



Specification
-------------

#### Encoding

`yaff` files must be text files encoded as valid UTF-8.
- A byte-order mark (`u+FEFF`) may be included at the start of the file.
- Lines must be terminated by one of the following line endings:
  `LF` (`u+000a`), `CR LF` (`u+000d u+000a`), or `CR` (`u+000d`).
- *Whitespace* consists of spaces (`u+0020`) and tabs (`u+0009`).
- A `yaff` file must not contain control characters, other than the ones mentioned
  above, or UTF-8 noncharacters.

#### Components
`yaff` files consist of *properties*, *glyph definitions*, and *comments*.
Each of these components is optional; an empty file is a valid (if pointless) `yaff` file.
Font properties must not follow glyph definitions.

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
* The key must be given at the start of the line. Leading whitespace is not allowed.
* The key and the separator `:` must be on the same line.

Whitespace between the key, the separator, and the value is allowed.
There may be at most one newline between the separator and the value.
* If there is no newline between the separator and the value, the value consists of the remainder
  of the line following the separator, excluding leading and trailing whitespace and the line ending.
* If there is a newline following the separator, the value consists of all following lines which start
  with whitespace. There must be at least one such line. Leading and trailing whitespace on these
  lines does not form part of the value, but the newlines do.
* A value may contain any character that is allowed in a `yaff` file.
* No line of a value must start with `:`, `.`, or `@`.
* No line of a value must end with `:`.
* No line of a value must be empty or consist of only the character `-`.
* If any line of a value starts and ends with a double quote character `"`,
  these quotes are stripped and everything in between is used unchanged.

#### Glyph definitions
A *glyph definition* consists of one or more *labels*, followed by a *glyph*. If there are multiple
labels, all are considered to point to the glyph that follows.

##### Labels
A *label* must be followed by a separator `:`, optional whitespace, and a line ending.
* The label must be given at the start of the line. Leading whitespace is not allowed.
* A label has one of three types: *character*, *codepoint*, or *tag*.

If a label starts with an ASCII digit, it is a *codepoint*.
* A codepoint label may consist of multiple elements, separated by commas and optional whitespace.
* Each element represents an unsigned integer value.
* If all characters in the element are digits, the element is in decimal format.
  Leading `0`s in decimals are allowed.
* If the first two characters are `0x` or `0X`, the element is hexadecimal. All further characters
  must be hex digits and are not case sensitive.
* If the first two characters are `0o` or `0O`, the element is octal. All further characters must
  be octal digits.
* If a codepoint label consists of multiple elements, each element must be less than 256.
  This forms a multi-byte codepoint sequence pointing to a single glyph.

Examples of valid codepoint labels are `32`, `0032`, `0x20`, `0o24`, (all of which refer to the same
codepoint). Further examples are `0x120`, `0x1, 0x20`, `1, 32` (all of which are the same multi-byte
codepoint sequence).


If a label:
* is enclosed by single quote characters `'`, **or**
* starts with `u+` or `U+`, **or**
* starts with a character that is not in 7-bit ASCII, **or**
* consists of a single Unicode character

it is a *character* label, which may be a grapheme sequence consisting of multiple Unicode code points.
* A character label may consist of multiple elements, separated by commas and optional whitespace.
* Each element must start with `u+` or `U+` or be enclosed in single quotes.
* If an element starts with `u+` or `U+`, it must be followed by hex digits. It represents a Unicode point in hexadecimal notation.
  The hex digits are not case sensitive.
* If a label element starts and ends with a single-quote character `'`,
  these quotes are stripped and the element consists of everything in between.

Examples of valid character labels are `A`, `À`, `安` (all of which are single characters), `ते`
(a grapheme sequence consisting of multiple non-ASCII characters), its equivalent `u+0924, u+0947`,
 and `'ffi'` (multiple characters enclosed in single quotes).

If a label:
* is enclosed in double quote characters `"`, **or**
* starts with an ASCII letter, is at least 2 characters long, and consists only of
  ASCII letters, ASCII digits, the underscore `_`, the dash `-`, or the full stop `.`,

it is a *tag*.
* Tags are case-sensitive and (if double-quoted) may contain any kind of character.
* If a label starts and ends with a double-quote character `"`,
  these quotes are stripped and the tag consists of everything in between.

##### Glyphs

A *glyph* may span multiple lines.
* The lines of a glyph must start with whitespace (the _indent_). Trailing whitespace is allowed.
* All lines of the glyph must have identical indent.
* If a glyph consists of the character `-` only, it is the empty glyph.
* Otherwise, the glyph must consist of the characters `.` and `@` only.
* After removal of whitespace, all lines in the glyph must be of equal length.
* A `@` represents an inked pixel in the glyph, a `.` represents an un-inked pixel.
* Per-glyph properties may follow the glyph definition. These must be at the same indent and
  separated from the pixel data by a blank line.


Recognised properties
---------------------

The following are font properties `monobit` is aware of. Other properties may be defined as and when needed.

##### Metrics

_Metrics_ are properties that affect how the font is rendered. There are per-glyph metrics and global metrics.

Global metrics are:
- `line-height`: Vertical spacing between consecutive baselines (for horizontal writing).
- `line-width`: Horizontal spacing between consecutive baselines (for vertical writing).

Per-glyph or global horizontal metrics are:
- `left-bearing`: Horizontal offset (in direction of writing) between leftward origin and left raster edge.
- `right-bearing`: Horizontal offset (in direction of writing) between rightward origin and right raster edge.
- `shift-up`: Upward shift from baseline to raster bottom edge.

Per-glyph or global vertical metrics are:
- `top-bearing`: Vertical offset (in direction of writing) between upward origin and top raster edge.
- `bottom-bearing`: Vertical offset (in direction of writing) between downward origin and bottom raster edge.
- `shift-left`: Leftward shift from baseline to central vertical axis of raster.

If these metrics are specified globally, they apply to all
glyphs. If metrics are specified both globally and per-glyph, they are added.

Per-glyph only metrics are:
- `right-kerning`: Adjustment to right bearing for specific glyph pairs. E.g. the pair `AV` may have negative
  kerning, so that they are displayed tighter than they otherwise would. Such an adjustment is
  specified in the `right-kerning` property of the `A` glyph, as a pair of the label for the `V` glyph and
  a numeric adjustment value.
- `left-kerning`: Adjustment to left bearing for specific glyph pairs. The same adjustment as above could be
  specified in the `left-kerning` property of the `V` glyph, as a pair of the label for the `A` glyph and
  a numeric adjustment value. If both `left-kerning` and `right-kerning` are specified, they add up.
- `scalable-width`: Advance width in fractional pixels, can be used for scaled rendering.
- `scalable-height`: Advance height in fractional pixels, can be used for scaled rendering.


##### Rendering hints

_Rendering hints_ affect the way decorations and transformations are applied. They are:
- `direction`: Advance direction of writing. The following directions are supported:
  - `left-to-right`: left to right, top to bottom
  - `right-to-left`: right to left, top to bottom
  - `top-to-bottom`: top to bottom, right to left
  If the glyphs in the font have character labels, the default is to determine horizontal writing
  direction algorithmically from Unicode properties. If no character labels are given, the
  default direction is `left-to-right`.
- `bold-smear`: additional number of pixels to trail ink by, when bolding algorithmically
- `italic-pitch`: pitch when italicising algorithmically, given as x,y step sizes
- `outline-thickness`: number of pixels in a generated outline
- `underline-thickness`: number of pixels in a generated underline
- `underline-descent`: location of underline in pixels below the baseline
- `superscript-size`: pixel size of superscript font to use
- `superscript-offset`: Horizontal (in direction of writing), upward offset for a superscript
- `subscript-size`: pixel size of subscript font to use
- `subscript-offset`: Horizontal (in direction of writing), downward offset for a subscript
- `small-cap-size`: pixel size of small-capital font to use
- `word-space`: normal space between words
- `min-word-space`: minimum space between words
- `max-word-space`: maximum space between words
- `sentence-space`: space between sentences


##### Characteristics

_Characteristics_ are descriptive in nature. They can be specified or calculated. Usually specified are:
- `x-height`: height of a lowercase `x` relative to the baseline.
- `cap-height`: height of a capital letter relative to the baseline.
- `ascent`: height of lowercase letters such as `f` that extend above the x-height.
- `descent`: extent of lowercase letters such as `j` below the baseline.
- `pixel-size`: pixel size (equals ascent plus descent).
- `leading`: additional vertical line spacing in excess of the `pixel-size`.
             Equals `line-height` less `pixel-size`.

For fonts with vertical metrics, the following may exist:
- `left-extent`: extent of glyphs to the left of the vertical baseline
                 (analogue of `descent`).
- `right-extent`: extent of glyphs to the right of the vertical baseline
                  (analogue of `ascent`).

Characteristics inferred from the glyphs are:
- `raster`: largest raster needed to define a glyph; coordinates (left, bottom, right, top)
- `ink-bounds`: smallest box that encompasses all ink if all glyphs are overlaid at the same origin.
                coordinates (left, bottom, right, top)
- `raster-size`: (width, height) of raster.
- `cell-size`: (width, height) of character cell - (0, 0) for proportional fonts.
- `bounding-box`: (width, height) of ink-bounds.
- `average-width`: average advance width across glyphs.
- `max-width`: maximum advance width across glyphs.
- `cap-width`: advance width of capital letter `X`.
- `digit-width`: advance width of digits and `$` sign, if all equal.
- `spacing`: type of font, can be one of:
  - `proportional`: glyphs have different advance widths, e.g. `M` is wider than `i`.
  - `monospace`: all glyphs have the same advance width.
  - `character-cell`: all glyphs can be defined on a raster of fixed size and displayed without overlap.
  - `multi-cell`: like `character-cell`, but some glyphs may take up two cells.

Characteristics that give a font's identity are:
- `family`: typeface or font family name
- `subfamily`: additional font name components; usually style, weight, slant
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
- `author`: author of the font
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


##### Encoding parameters

_Encoding parameters_ affect how text is converted into glyphs.

- `encoding`: name of the codepage or encoding that matches codepoints to characters, e.g. `unicode`, `oem-437`.
- `default-char`: label indicating the glyph to be used as the _missing_, _undefined_ or _default_ glyph
- `word-boundary`: label indicating the glyph to be used as a word boundary. Usually u+0020 (space).


##### Stroke definitions

- `path` is a glyph property that contains a stroke sequence describing
    how to draw the glyph. The stroke path is defined as a sequence of straight lines
    and moves to be applied sequentially, starting from the glyph origin.
    Path elements are given as a keyword followed by relative x,y offsets where the x coordinate
    increases rightward and the y coordinate increases upward.
        `m` _x_ _y_ moves _x_ design units to the right and _y_ design units up
        `l` _x_ _y_ draws a line _x_ design units to the right and _y_ design units up
    Stroke definitions are scalable and can be converted to pixel values by applying
    a scaling factor, which may differ between x and y directions but must be
    constant across path elements. The glyph bitmap to which the `path` property
    attaches may be empty (`-`) or a realisation of the stroke drawing.


##### Deprecated properties

The following properties are recognised for backward compatibility, but
should not be used in new files:

Per-glyph:
- `offset` (_x_ _y_ pair): equal to (`left-bearing`, `shift-up`).
- `tracking`: equal to `right-bearing`.
- `kern-to`: equal to `right-kerning`.

Global:
- `average-advance`: equal to `average-width`.
- `max-advance`: equal to `max-width`.
- `cap-advance`: equal to `cap-width`.


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
                ┴       ┬   ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤            ┴
    pixel-size = 6  │   │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▓│   │ │ │ │            descent = 1
                    ┴       X─┴─┴─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘
    raster-size.y = 8   │
                            ┌─┬─┬─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐  ─┬─┬─┬─┐ . . top-line
                        │   │ │ │ │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │ │   │ │ │ │
                        ┴   ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . ascent-line
              leading = 3   │ │ │ │ │ │ │   │ │ │ │   │ │█│ │   │ │█│█│   │ │ │█│   │ │ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . cap-line
                            │ │ │ │ │█│ │   │ │ │ │   │ │ │ │   │█│ │ │   │ │ │ │   │ │ │█│
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . mean-line
                            │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│█│ │   │ │ │█│   │ │█│ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
                            │ │ │ │█│█│█│   │ │█│ │   │█│ │█│   │█│ │ │   │ │ │█│   │█│ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤
            shift-up = -2   │ │ │ │█│ │█│   │█│ │█│   │ │█│█│   │█│ │ │   │ │ │█│  ▓│ │ │ │
                        O   ├─┼─┼─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤  ─O─┼─┼─┤ . . baseline
                        │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │█│█│ │▓  │ │ │ │
                            ├─┼─┼─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤  ─┼─┼─┼─┤ . . descent-line
                        │   │ │ │ │ │ │ │   │ │ │ │   │ │ │ │   │ │ │ │   │ │ │▓│   │ │ │ │
                        X   X─┴─┴─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘  ─┴─┴─┴─┘ . . bottom-line

                            X─ ─ ─O left-bearing = -3

          raster-size.x = 6 ├─ ─ ─ ─ ─ ─┤
                                  O─ ─ ─ ─ ─O advance-width = 5
                                        ├─ ─O right-bearing = 2


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
