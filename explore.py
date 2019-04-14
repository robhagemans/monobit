#!/usr/bin/env python3
"""
Draw contents of a binary file as bitmap
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""
import sys
import argparse

BGCHAR = u'-'
FGCHAR = u'#'

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin.buffer)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument(
    '-s', '--stride', default=1, type=int,
    help='number of bytes per scanline'
)
args = parser.parse_args()


rombytes = args.infile.read()
rows = [u'{:08b}'.format(_c) for _c in bytearray(rombytes)]
drawn = [_row.replace(u'0', BGCHAR).replace(u'1', FGCHAR) for _row in rows]


for offset in range(0, len(drawn), args.stride):
    ordinal = offset // args.stride
    char = drawn[offset:offset+args.stride]
    args.outfile.write(u'{:04x}: '.format(ordinal))
    args.outfile.write(u''.join(char))
    args.outfile.write(u'\n')
