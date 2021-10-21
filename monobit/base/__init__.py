"""
monobit.base - shared utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


DEFAULT_FORMAT = 'yaff'
VERSION = '0.17'

CONVERTER_NAME = f'monobit v{VERSION}'


def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}
