#!/usr/bin/env python3
"""
Draw contents of a binary file as bitmap to image
(c) 2019--2022 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
from PIL import Image, ImageDraw, ImageFont

def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)


# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin.buffer)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '-s', '--stride-from', default=1, type=int,
    help='number of bytes per scanline'
)
parser.add_argument(
    '-t', '--stride-to', default=None, type=int,
    help='number of bytes per scanline'
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
    help='number of vertical pixels between character cells'
)
parser.add_argument(
    '--margin', default=10, type=int,
    help='number of horizontal pixels left of first bitmap'
)
parser.add_argument(
    '--scale', default=4, type=int,
    help='number of horizontal and vertical pixels in image that make up a pixel in the font'
)

args = parser.parse_args()

args.infile.read(args.offset)
rombytes = args.infile.read(args.bytes)
rows = ['{:08b}'.format(_c) for _c in rombytes]

scale = args.scale
margin = args.margin
padding = args.padding

images = []
if args.stride_to is None:
    args.stride_to = args.stride_from + 1

for stride in range(args.stride_from, args.stride_to):
    width = stride * 8
    height = ceildiv(len(rombytes), stride)

    if args.image:
        fore, back, border = (255, 255, 255), (0, 0, 0), (20, 20, 20)

        img = Image.new('RGB', (width, height), border)
        data = [
            fore if _c == '1' else back
            for _row in rows
            for _c in _row
        ]
        img.putdata(data)
        images.append((stride, img))
    else:
        if args.stride_to > args.stride_from + 1:
            args.outfile.write('\n')
            title = f'stride={stride}'
            args.outfile.write(title + '\n')
            args.outfile.write('-'*len(title) + '\n')

        drawn = [_row.replace(u'0', args.paper).replace(u'1', args.ink) for _row in rows]
        decwidth = len(str(len(drawn)))
        hexwidth = len(hex(len(drawn))) - 2

        for offset in range(0, len(drawn), stride):
            char = drawn[offset:offset+stride]
            args.outfile.write('{offset:{decwidth}} {offset:0{hexwidth}x}: '.format(
                offset=offset, decwidth=decwidth, hexwidth=hexwidth
            ))
            args.outfile.write(''.join(char))
            args.outfile.write('\n')

if args.image:
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

    fullimage = fullimage.resize((fullimage.width * scale, fullimage.height * scale))
    fullimage.show()
