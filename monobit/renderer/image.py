"""
monobit.renderer.image - support for rendering to image

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import safe_import
Image = safe_import('PIL.Image')


DEFAULT_IMAGE_FORMAT = 'png'

IMAGE_PATTERNS = (
    '*.png', '*.bmp', '*.gif', '*.tif', '*.tiff',
    '*.ppm', '*.pgm', '*.pbm', '*.pnm', '*.webp',
    '*.pcx', '*.tga', '*.jpg', '*.jpeg',
)

IMAGE_MAGIC = (
    # PNG
    b'\x89PNG\r\n\x1a\n',
    # BMP
    #b'BM',   # -- clash with bmfont b'BMF'
    # GIF
    b'GIF87a', b'GIF89a',
    # TIFF
    b'\x4D\x4D\x00\x2A', b'\x49\x49\x2A\x00'
    # PNM
    b'P1', b'P2', b'P3',
    # WebP
    b'RIFF',
    # PCX
    b'\n\x00', b'\n\x02', b'\n\x03', b'\n\x04', b'\n\x05',
    # JPEG
    b'\xFF\xD8\xFF',
)


def write_imagefile(outfile, img, image_format):
    """Write a PIL image to file."""
    try:
        img.save(outfile, format=image_format or Path(outfile).suffix[1:])
    except (KeyError, ValueError, TypeError):
        img.save(outfile, format=DEFAULT_IMAGE_FORMAT)
