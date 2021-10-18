#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main, convert_script_args, repr_script_args, add_script_args


# parse command line
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument(
    'operation', nargs=1, choices=sorted(monobit.operations),
    help='\n'.join(
        f"{_name}: {_func.__doc__.strip()}"
        for _name, _func in monobit.operations.items()
    )
)

parser.add_argument('--infile', type=str, default='')
parser.add_argument('--outfile', type=str, default='')

parser.add_argument(
    '--overwrite', action='store_true',
    help='overwrite existing output file'
)
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)


# find out which operation we're asked to perform
args, unknown = parser.parse_known_args()

# get arguments for this operation
operation_name = args.operation[0]
operation = monobit.operations[operation_name]
add_script_args(parser, operation)

args = parser.parse_args()

# convert script arguments to type accepted by operation
fargs = convert_script_args(operation, vars(args))


with main(args, logging.WARNING):

    # load
    fonts = monobit.load(args.infile or sys.stdin)

    # modify
    fonts = tuple(
        operation(_font, **fargs)
        for _font in fonts
    )

    # record converter parameters
    fonts = tuple(
        _font.set_properties(
            converter_parameters=(
                ((_font.converter_parameters + '\n') if hasattr(_font, 'converter_parameters') else '')
                + repr_script_args(operation_name, vars(args), operation)
            )
        )
        for _font in fonts
    )

    # save
    monobit.save(fonts, args.outfile or sys.stdout, overwrite=args.overwrite)
