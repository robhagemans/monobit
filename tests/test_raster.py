"""
monobit test suite
raster ink-level tests
"""

import unittest

from monobit.core.raster import Raster


class TestRaster(unittest.TestCase):
    """Test raster ink levels."""

    def test_rescale_ink(self):
        """Rescaling preserves each pixel's share of full ink."""
        raster = Raster.from_matrix([[0, 1], [7, 3]], inklevels=range(8))
        rescaled = raster.rescale_ink(16)
        self.assertEqual(rescaled.levels, 16)
        self.assertEqual(rescaled.as_matrix(), ((0, 2), (15, 6)))


if __name__ == '__main__':
    unittest.main()
