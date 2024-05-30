"""
monobit.storage.base - storage

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .magic import MagicRegistry

DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'

loaders = MagicRegistry(DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT)
savers = MagicRegistry(DEFAULT_TEXT_FORMAT)
containers = MagicRegistry()
wrappers = MagicRegistry()
