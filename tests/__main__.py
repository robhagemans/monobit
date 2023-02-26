"""
monobit test suite
"""

import unittest

if __name__ == '__main__':
    suite = unittest.TestLoader().discover('.')
    unittest.TextTestRunner().run(suite)
