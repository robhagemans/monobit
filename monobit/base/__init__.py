"""
monobit.base - shared utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


DEFAULT_FORMAT = 'yaff'
VERSION = '0.15'

CONVERTER_NAME = f'monobit v{VERSION}'


def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn

def boolean(boolstr):
    """Convert str to bool."""
    return boolstr.lower() == 'true'

def pair(pairstr):
    """Convert NxN or N,N to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

# also works for 3-tuples...
rgb = pair

def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}
