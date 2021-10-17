"""
monobit.base.image - utilities to deal with images

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


try:
    from PIL import Image
except ImportError:
    Image = None


def to_image(matrix, border=(32, 32, 32), paper=(0, 0, 0), ink=(255, 255, 255)):
    """Convert matrix to image."""
    if not Image:
        raise ImportError('Rendering to image requires PIL module.')
    height = len(matrix)
    if height:
        width = len(matrix[0])
    else:
        width = 0
    img = Image.new('RGB', (width, height), border)
    img.putdata([{-1: border, 0: paper, 1: ink}[_pix] for _row in matrix for _pix in _row])
    return img
