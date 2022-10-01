#!/usr/bin/env python3
"""
Draw contents of a binary file as bitmap
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""
import sys
import argparse

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin.buffer)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '-s', '--stride', default=1, type=int,
    help='number of bytes per scanline'
)
parser.add_argument(
    '--ink', '--foreground', '-fg', type=str, default='@',
    help='character to use for ink/foreground (default: @)'
)
parser.add_argument(
    '--paper', '--background', '-bg', type=str, default='-',
    help='character to use for paper/background (default: -)'
)
args = parser.parse_args()


rombytes = args.infile.read()
rows = [u'{:08b}'.format(_c) for _c in bytearray(rombytes)]
drawn = [_row.replace(u'0', args.paper).replace(u'1', args.ink) for _row in rows]

decwidth = len(str(len(drawn)))
hexwidth = len(hex(len(drawn))) - 2

for offset in range(0, len(drawn), args.stride):
    #ordinal = offset // args.stride
    char = drawn[offset:offset+args.stride]
    args.outfile.write('{offset:{decwidth}} {offset:0{hexwidth}x}: '.format(
        offset=offset, decwidth=decwidth, hexwidth=hexwidth
    ))
    args.outfile.write(''.join(char))
    args.outfile.write('\n')
