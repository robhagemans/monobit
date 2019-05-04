#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit


def anyint(instr):
    """Convert dec/hex/oct string to integer."""
    return int(instr, 0)

CONVERTERS = {
    int: anyint,
    #bool
    #dict
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
converters = {_arg: CONVERTERS[_type] for _arg, _type in operation.script_args.items()}

for arg in converters:
    parser.add_argument('--' + arg.strip('_'), dest=arg)
args = parser.parse_args()

# convert arguments to type accepted by operation
fargs = {
    _name: _conv(args.__dict__[_name])
    for _name, _conv in converters.items()
    if args.__dict__[_name] is not None
}

# load, modify, save
font = monobit.load(args.infile)
font = operation(font, **fargs)
font.save(args.outfile)
