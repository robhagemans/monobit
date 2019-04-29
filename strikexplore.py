#!/usr/bin/env python3
"""
Draw contents of a binary file as bitmap to image
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
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
rows = ['{:08b}'.format(_c) for _c in bytearray(rombytes)]

scale = args.scale
margin = args.margin
padding = args.padding

images = []
if args.stride_to is None:
    args.stride_to = args.sride_from + 1
for stride in range(args.stride_from, args.stride_to):
    width = stride * 8
    height = ceildiv(len(rombytes), stride)

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
    draw.text((0, top), str(stride), font=font)
    fullimage.paste(img, (left, top))
    top += img.height + padding

fullimage = fullimage.resize((fullimage.width * scale, fullimage.height * scale))
fullimage.show()
