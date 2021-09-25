#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2020 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit


def str_to_int(instr):
    """Convert dec/hex/oct string to integer."""
    return int(instr, 0)


CONVERTERS = {
    int: str_to_int,
    bool: bool,
    str: str,
}


logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('operation', nargs='+', choices=monobit.OPERATIONS.keys())
parser.add_argument('--infile', type=str, default='')
parser.add_argument('--outfile', type=str, default='')

# find out which operation we're asked to perform
args, unknown = parser.parse_known_args()

# get arguments for this operation
operation = monobit.OPERATIONS[args.operation[0]]
for arg, _type in operation.script_args.items():
    if _type == bool:
        parser.add_argument('--' + arg.strip('_'), dest=arg, action='store_true')
    else:
        parser.add_argument('--' + arg.strip('_'), dest=arg, type=CONVERTERS[_type])

args = parser.parse_args()

# convert arguments to type accepted by operation
fargs = {
    _name: _arg
    for _name, _arg in args.__dict__.items()
    if _arg is not None and _name in operation.script_args
}

# load, modify, save
try:
    if not args.infile:
        args.infile = sys.stdin.buffer
    font = monobit.load(args.infile)
    font = getattr(font, args.operation[0])(**fargs)
    if not args.outfile:
        args.outfile = sys.stdout.buffer
    monobit.save(font, args.outfile)
except Exception as exc:
    logging.error(exc)
