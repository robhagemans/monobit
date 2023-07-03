"""
Print a banner using a bitmap font
(c) 2019--2023 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""


import sys
import argparse
import logging
import codecs
from codecs import escape_decode

import monobit
from monobit.scripting import wrap_main
from monobit.basetypes import Coord, RGB
from monobit.renderer import render
from monobit.font import Font


def unescape(text):
    """Interpolate escape sequences."""
    # escape_decode is undocumented/unsupported and will leave \u escapes untouched
    # simpler variant - using documented/supported codecs
    #   raw-unicode-escape encodes to latin-1, leaves existing backslashes untouched but escapes non-latin-1
    #   (while unicode-escape would escape backslashes and all non-ascii)
    #   unicode-escape decodes from latin-1 and unescapes standard c escapes, \x.. and \u.. \U..
    return text.encode('raw-unicode-escape').decode('unicode_escape')


def register_handler(handler_name, default_char):
    """Register an encode/decode error handler with custom replacement char."""
    def _handler(e):
        return default_char, e.end
    codecs.register_error(handler_name, _handler)


def main():
    # parse command line
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'text', nargs='*', type=str, action='extend',
        help=(
            'text to be printed. '
            'multiple text arguments represent consecutive lines. '
            'if not given, read from standard input'
        )
    )
    parser.add_argument(
        '--text', nargs='*', type=str, action='extend',
        help=(
            'text to be printed. '
            'multiple text arguments represent consecutive lines. '
            'if not given, read from standard input'
        )
    )
    parser.add_argument(
        '--font', '-f', type=str, default='',
        help='font file to use when printng text'
    )
    parser.add_argument(
        '--format', type=str, default='',
        help='format of file used in --font'
    )
    parser.add_argument(
        '--ink', '--foreground', '-fg', type=str, default='',
        help=(
            'character or colour to use for ink/foreground '
            '(default: @ or (0,0,0))'
        )
    )
    parser.add_argument(
        '--paper', '--background', '-bg', type=str, default='',
        help=(
            'character or colour to use for paper/background '
            '(default: . or (255,255,255))'
        )
    )
    parser.add_argument(
        '--border', type=str, default='',
        help=(
            'character or colour to use for border '
            '(default: same as paper)'
        )
    )
    parser.add_argument(
        '--margin', '-m', type=Coord.create, default=None,
        help=(
            'number of background characters to use as a margin '
            'in x and y direction (default: minimum necessary)'
        )
    )
    parser.add_argument(
        '--scale', '-s', type=Coord.create, default=(1, 1),
        help=(
            'number of characters to use per pixel in x and y direction '
            '(default: 1,1)'
        )
    )
    parser.add_argument(
        '--rotate', '-r', type=int, default=0,
        help='number of quarter turns to rotate (default: 0)'
    )
    parser.add_argument(
        '--direction', type=str, default='',
        help=(
            "writing direction (default: use bidirectional algorithm;"
            " other options: `l`==`left-to-right`, `r`==`right-to-left`, "
            "`t`==`top-to-bottom`, `b`==`bottom-to-top`). "
            "May be combined as primary, secondary direction separated by space."
        )
    )
    parser.add_argument(
        '--align', type=str, default='',
        help=(
            "text alignment. (default: left for left-to-right, etc. "
            " other options: `l`==`left`, `r`==`right`, "
            "`t`==`top`, `b`==`bottom`)"
        )
    )
    parser.add_argument(
        '--encoding', default='', type=str,
        help='override encoding/codepage (default: infer from metadata in file)'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='show debugging output'
    )
    parser.add_argument(
        '--output',  default='', type=str,
        help=(
            'output file name. use .txt extension for text output, '
            'or image format for image output'
        )
    )
    parser.add_argument(
        '--image',  action='store_true',
        help=('output as image')
    )
    parser.add_argument(
        '--blocks',  nargs='?', const='2x2', default='',
        help=('output as block element characters')
    )
    # font / glyph effects
    parser.add_argument(
        '--bold', action='store_true',
        help='apply algorithmic bold effect'
    )
    parser.add_argument(
        '--italic', action='store_true',
        help='apply algorithmic italic effect'
    )
    parser.add_argument(
        '--underline', action='store_true',
        help='apply algorithmic underline effect'
    )
    parser.add_argument(
        '--outline', action='store_true',
        help='apply algorithmic glyph outline effect'
    )
    parser.add_argument(
        '--expand', type=int, default=0,
        help=(
            'adjust bearings by given number of pixels '
            'wider (positive) or tighter (negative)'
        )
    )
    args = parser.parse_args()

    with wrap_main(args.debug):
        #######################################################################
        # deal with inputs
        # read text from stdin if not supplied
        if not args.text:
            args.text = sys.stdin.read()
        else:
            # multiple options or \n give line breaks
            args.text = '\n'.join(args.text)
        # foreground and backgound characters
        args.ink = unescape(args.ink)
        args.paper = unescape(args.paper)
        args.border = unescape(args.border)
        args.text = unescape(args.text)
        #######################################################################
        # take first font from pack
        font, *_ = monobit.load(args.font, format=args.format)
        #######################################################################
        # encoding
        # check if any characters are defined
        # override encoding if requested
        if (
                not font.get_chars()
                and not args.encoding
                and not isinstance(args.text, bytes)
            ):
            logging.info(
                'No character mapping defined in font. '
                'Using `--encoding=raw` as fallback.'
            )
            args.encoding = 'raw'
        if args.encoding == 'raw':
            # register the codepoint for replacement char
            # note that we use latin-1 strings to represent bytes here
            # if no replacement char or it has no codepoint, replace with empty
            default_cp = font.get_default_glyph().codepoint.decode('latin-1')
            register_handler('custom_replace', default_cp)
            # see input string as a sequence of bytes to render through codepage
            # replace anything with more than 8-bit codepoints
            args.text = args.text.encode('latin-1', errors='custom_replace')
        elif args.encoding:
            font = font.modify(encoding=args.encoding).label()
        #######################################################################
        # line up effects
        # these use default arguments as defined by rendering hints
        transformations  = []
        if args.bold:
            transformations.append((Font.smear, (), {}))
        if args.italic:
            transformations.append((Font.shear, (), {}))
        if args.underline:
            transformations.append((Font.underline, (), {}))
        if args.outline:
            transformations.append((Font.outline, (), {}))
        #######################################################################
        # render
        glyph_map = render(
            font, args.text,
            margin=args.margin,
            direction=args.direction, align=args.align, adjust_bearings=args.expand,
            missing='default',
            transformations=transformations,
        )
        # transformations
        glyph_map.stretch(*args.scale)
        glyph_map.turn(clockwise=args.rotate)
        #######################################################################
        # output
        if args.image or args.output and not args.output.endswith('.txt'):
            ink = RGB.create(args.ink or (0, 0, 0))
            paper = RGB.create(args.paper or (255, 255, 255))
            border = RGB.create(args.border) if args.border else paper
            image = glyph_map.as_image(ink=ink, paper=paper, border=border)
            if args.output:
                image.save(args.output)
            else:
                image.show()
        else:
            if args.blocks:
                resolution = tuple(int(_v) for _v in args.blocks.split('x'))
                text = glyph_map.as_blocks(resolution)
            else:
                ink = args.ink or '@'
                paper = args.paper or '.'
                border = args.border or paper
                text = glyph_map.as_text(ink=ink, paper=paper, border=border) + '\n'
            if not args.output:
                sys.stdout.write(text)
            else:
                with open(args.output, 'w') as outfile:
                    outfile.write(text)


if __name__ == '__main__':
    main()
