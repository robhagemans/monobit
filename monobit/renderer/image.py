"""
monobit.renderer.image - support for rendering to image

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.storage.magic import Magic


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
    b'BM' + Magic.offset(10) + b'\0\0\c\0\0\0' + Magic.offset(4) + b'\1\0' + Magic.offset(1) + b'\0',
    b'BM' + Magic.offset(10) + b'\0\0' + Magic.offset(1) + b'\0\0\0' + Magic.offset(8) + b'\1\0' + Magic.offset(1) + b'\0',
    # GIF
    b'GIF87a', b'GIF89a',
    # TIFF
    b'\x4D\x4D\x00\x2A', b'\x49\x49\x2A\x00'
    # PNM
    b'P1', b'P2', b'P3', b'P4', b'P5', b'P6',
    # WebP
    b'RIFF' + Magic.offset(4) + b'WEBP',
    # PCX
    b'\n\x00', b'\n\x02', b'\n\x03', b'\n\x04', b'\n\x05',
    # JPEG
    b'\xFF\xD8\xFF',
)


def write_imagefile(outfile, img, image_format):
    """Write a PIL image to file."""
    try:
        img.save(outfile, format=image_format or None)
    except (KeyError, ValueError, TypeError) as e:
        img.save(outfile, format=DEFAULT_IMAGE_FORMAT)
