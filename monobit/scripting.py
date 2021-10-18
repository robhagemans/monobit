"""
monobit.scripting - scripting utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn


# script type converters

def boolean(boolstr):
    """Convert str to bool."""
    return boolstr.lower() == 'true'

def _tuple(pairstr):
    """Convert NxNx... or N,N,... to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

rgb = _tuple
pair = _tuple
