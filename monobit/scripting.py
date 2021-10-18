"""
monobit.scripting - scripting utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# mark functions for scripting

def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.script_args = fn.__annotations__
    return fn

def get_scriptables(cls):
    return {
        _name: _func
        for _name, _func in cls.__dict__.items()
        if not _name.startswith('_') and hasattr(_func, 'script_args')
    }


# script type converters

def boolean(boolstr):
    """Convert str to bool."""
    return boolstr.lower() == 'true'

def _tuple(pairstr):
    """Convert NxNx... or N,N,... to tuple."""
    return tuple(int(_s) for _s in pairstr.replace('x', ',').split(','))

rgb = _tuple
pair = _tuple
