#!/usr/bin/env python3
"""
Bit dump binary file to text or image.
Text output is like `xxd` but more adapted to visually exploring bitmaps.

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging
from PIL import Image, ImageDraw, ImageFont
from itertools import zip_longest
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument(
    'infile', nargs='?',
    type=argparse.FileType('rb'), default=sys.stdin.buffer
)
parser.add_argument(
    'outfile', nargs='?',
    type=str, default=''
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
    '-b', '--stride-bits', default=None, type=int,
    help='bits per scanline. cannot be used with -s or -t'
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
    '--paper', '--background', '-bg', type=str, default='.',
    help='character to use for paper/background (default: .)'
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
    '--scale', default=1, type=int,
    help='number of horizontal and vertical pixels used to represent a single bit'
)


def main():
    args = parser.parse_args()

    if args.stride_to is None:
        args.stride_to = args.stride_from

    args.infile.read(args.offset)
    data = args.infile.read(args.bytes)
    bytesize = len(data)

    if args.image or args.outfile and not args.outfile.endswith('.txt'):
        if args.stride_bits is not None:
            raise ValueError('Bit-aligned strides not supported for images.')
        # output filename does not end with .txt
        # see if PIL recognises the suffix, otherwise dump as text
        try:
            return bitdump_image(
                args.outfile,
                data, bytesize, args.stride_from, args.stride_to,
                args.margin, args.padding, args.scale
            )
        except ValueError as e:
            # unknown file extension
            if not str(e).startswith('unknown file extension'):
                raise
            logging.warning(
                'Output file extension `%s` not recognised, using text output.',
                Path(args.outfile).suffix
            )
    try:
        bitdump_text(
            args.outfile,
            data, bytesize,
            args.stride_from, args.stride_to, args.stride_bits,
            args.paper, args.ink, start=args.offset
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


def draw_bits(data, paper, ink):
    bits = bin(int.from_bytes(data, 'big'))[2:].zfill(8*len(data))
    return bits.replace('0', paper).replace('1', ink)


def bitdump_text(
        outfilename,
        data, bytesize,
        stride_from, stride_to, stride_bits,
        paper, ink, start
    ):
    """Bit dump to text output."""
    # width of decimal and hex offset fields
    decwidth = len(str(len(data)))
    hexwidth = len(hex(len(data))) - 2

    if outfilename:
        outfile = open(outfilename, 'w')
    else:
        outfile = sys.stdout

    if stride_bits is not None:
        # get the bits
        drawn = draw_bits(data, paper, ink)
        # itertools grouper
        args = [iter(drawn)] * stride_bits
        grouper = zip_longest(*args, fillvalue='0')
        for i, bits in enumerate(grouper):
            offset, mod = divmod(i * stride_bits, 8)
            if not mod:
                outfile.write(f'{offset+start:{decwidth}} {offset+start:0{hexwidth}x}  ')
            else:
                outfile.write(' ' * (decwidth + hexwidth + 3))
            outfile.write(''.join(bits))
            outfile.write('\n')
        return

    for stride in range(stride_from, stride_to+1):
        width = stride * 8
        height = ceildiv(bytesize, stride)

        if stride_to > stride_from:
            outfile.write('\n')
            title = f'stride={stride}'
            outfile.write(title + '\n')
            outfile.write('-'*len(title) + '\n')

        for offset in range(0, bytesize, stride):
            values = data[offset:offset+stride]
            bits = draw_bits(values, paper, ink)
            letters = ''.join(showchar(_v) for _v in values)
            outfile.write(f'{offset+start:{decwidth}} {offset+start:0{hexwidth}x}  ')
            outfile.write(bits)
            outfile.write(f'  {values.hex(" ")}  {letters}  ')
            outfile.write(' '.join(f'{_v:3d}' for _v in values))
            outfile.write('\n')

    if outfile != sys.stdout:
        outfile.close()

def bitdump_image(
        outfilename,
        data, bytesize,
        stride_from, stride_to,
        margin, padding, scale
    ):
    """Bit dump to image."""
    # colours
    border = (20, 20, 20)
    textcolour = (128, 255, 128)

    images = []
    # append more than enough zeros to fill any shortfall
    data += b'\0' * stride_to
    for stride in range(stride_from, stride_to+1):
        width = stride * 8
        height = ceildiv(bytesize, stride)
        img = Image.frombytes('1', (width, height), data)
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
        draw.text((0, top), str(stride), font=font, fill=textcolour)
        fullimage.paste(img, (left, top))
        top += img.height + padding

    fullimage = fullimage.resize((
        fullimage.width * scale,
        fullimage.height * scale
    ))
    if not outfilename:
        fullimage.show()
    else:
        fullimage.save(outfilename)

main()
