#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main


# parse command line
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

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
subparsers = parser.add_subparsers(dest='operation')

for name, func in monobit.operations.items():
    sub = subparsers.add_parser(name, help=func.__doc__)
    sub.set_defaults(func=func)
    sub.set_defaults(sub=sub)
    for arg, typ in func.script_args.items():
        sub.add_argument(f'--{arg}', type=typ)


# find out which operation we're asked to perform
args, _ = parser.parse_known_args()
operation = args.func

# get operation arguments
kwargs = vars(args.sub.parse_known_args()[0])
kwargs.pop('func')
kwargs.pop('sub')

# force error on unknown arguments
parser.parse_args()


with main(args, logging.WARNING):

    # load
    fonts = monobit.load(args.infile or sys.stdin)

    # modify
    fonts = tuple(
        operation(_font, **kwargs)
        for _font in fonts
    )

    # save
    monobit.save(fonts, args.outfile or sys.stdout, overwrite=args.overwrite)
