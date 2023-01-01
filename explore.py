#!/usr/bin/env python3
"""
Bit dump binary file to text or image.
Text output is like `xxd` but more adapted to visually exploring bitmaps.

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
from PIL import Image, ImageDraw, ImageFont


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument(
    'infile', nargs='?',
    type=argparse.FileType('rb'), default=sys.stdin.buffer
)
parser.add_argument(
    'outfile', nargs='?',
    type=argparse.FileType('w'), default=sys.stdout
)
parser.add_argument(
    '-s', '--stride-from', default=1, type=int,
    help='lowest number of bytes per scanline'
)
parser.add_argument(
    '-t', '--stride-to', default=None, type=int,
    help='highest number of bytes per scanline'
)
parser.add_argument(
    '-o', '--offset', default=0, type=int,
    help='byte offset into binary'
)
parser.add_argument(
    '-n', '--bytes', default=-1, type=int,
    help='total number of bytes to extract'
)
parser.add_argument(
    '--image', default=False, action='store_true',
    help='output as image instead of text'
)

# only apply to text

parser.add_argument(
    '--ink', '--foreground', '-fg', type=str, default='@',
    help='character to use for ink/foreground (default: @)'
)
parser.add_argument(
    '--paper', '--background', '-bg', type=str, default='-',
    help='character to use for paper/background (default: -)'
)

# only apply to images

parser.add_argument(
    '--padding', default=8, type=int,
    help='number of vertical pixels between output bitmaps'
)
parser.add_argument(
    '--margin', default=10, type=int,
    help='number of horizontal pixels left of first bitmap'
)
parser.add_argument(
    '--scale', default=4, type=int,
    help='number of horizontal and vertical pixels used to represent a single bit'
)


def main():
    args = parser.parse_args()

    if args.stride_to is None:
        args.stride_to = args.stride_from

    args.infile.read(args.offset)
    data = args.infile.read(args.bytes)
    bytesize = len(data)

    if args.image:
        bitdump_image(
            data, bytesize, args.stride_from, args.stride_to,
            args.margin, args.padding, args.scale
        )
    else:
        try:
            bitdump_text(
                args.outfile,
                data, bytesize, args.stride_from, args.stride_to,
                args.paper, args.ink
            )
        except BrokenPipeError:
            pass


def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)

def showchar(value):
    """Show ascii chars, replace non-ascii with shaded block elementss."""
    if value == 0:
        return '░'
    elif value < 0x20:
        return '▒'
    elif value == 0xff:
        return '█'
    elif value >= 0x7f:
        return '▓'
    return chr(value)

def bitdump_text(
        outfile,
        data, bytesize,
        stride_from, stride_to,
        paper, ink
    ):
    """Bit dump to text output."""
    rows = tuple('{:08b}'.format(_c) for _c in data)
    drawn = ''.join(
        _row.replace(u'0', paper).replace(u'1', ink)
        for _row in rows
    )

    for stride in range(stride_from, stride_to+1):
        width = stride * 8
        height = ceildiv(bytesize, stride)

        if stride_to > stride_from:
            outfile.write('\n')
            title = f'stride={stride}'
            outfile.write(title + '\n')
            outfile.write('-'*len(title) + '\n')

        decwidth = len(str(len(drawn)))
        hexwidth = len(hex(len(drawn))) - 2

        for offset in range(0, bytesize, stride):
            bits = drawn[offset*8:(offset+stride)*8]
            values = data[offset:offset+stride]
            letters = ''.join(showchar(_v) for _v in values)
            outfile.write(f'{offset:{decwidth}} {offset:0{hexwidth}x}  ')
            outfile.write(bits)
            outfile.write(f'  {values.hex(" ")}  {letters}  ')
            outfile.write(' '.join(f'{_v:3d}' for _v in values))
            outfile.write('\n')


def bitdump_image(
        data, bytesize,
        stride_from, stride_to,
        margin, padding, scale
    ):
    """Bit dump to image."""
    rows = ['{:08b}'.format(_c) for _c in data]

    images = []
    for stride in range(stride_from, stride_to+1):
        width = stride * 8
        height = ceildiv(bytesize, stride)

        fore, back, border = (255, 255, 255), (0, 0, 0), (20, 20, 20)

        img = Image.new('RGB', (width, height), border)
        data = [
            fore if _c == '1' else back
            for _row in rows
            for _c in _row
        ]
        img.putdata(data)
        images.append((stride, img))

    font = ImageFont.load_default()
    max_stride, _ = images[-1]
    size = font.getsize(str(max_stride))
    margin += size[0]

    fullimage = Image.new(
        'RGB', (
            margin + max(_i.width for _, _i in images),
            sum(_i.height + padding for _, _i in images)
        ),
        border
    )
    draw = ImageDraw.Draw(fullimage)
    left, top = margin, 0
    for stride, img in images:
        draw.text((0, top), str(stride), font=font, fill=(128, 255, 128))
        fullimage.paste(img, (left, top))
        top += img.height + padding

    fullimage = fullimage.resize((
        fullimage.width * scale,
        fullimage.height * scale
    ))
    fullimage.show()


main()
