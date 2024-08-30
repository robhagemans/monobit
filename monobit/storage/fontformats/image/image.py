"""
monobit.storage.fontformats.image.image - fonts stored in image files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import Counter
from pathlib import Path

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.base import Coord, RGB, FileFormatError, UnsupportedError
from monobit.base.binary import ceildiv
from monobit.storage.base import (
    loaders, savers, container_loaders, container_savers
)
from monobit.core import Font, Glyph, Codepoint
from monobit.render import create_chart, glyph_to_image, grid_traverser
from monobit.storage.utils.limitations import ensure_single
from monobit.storage.utils.perglyph import loop_load, loop_save


DEFAULT_IMAGE_FORMAT = 'png'


# available background policies
# -----------------------------
#
# most-common       use colour most commonly found in payload cells
# least-common      use colour least commonly found in payload cells
# brightest         use brightest colour, by sum of RGB values
# darkest           use darkest colour, by sum of RGB values
# top-left          use colour of top-left pixel in first cell

def identify_inklevels(colours, background):
    """Identify ink levels from colour set."""
    colourset = set(colours)
    if len(colourset) < 2:
        raise FileFormatError('No glyphs or only blank glyphs found.')
    elif len(colourset) > 2:
        # 3 or more non-border colours, must be a greyscale image
        if not all(
                len(set(_c[:3])) == 1 and not _c[3:] or _c[3] == 255
                for _c in colourset
            ):
            # only greyscale allowed, r==g==b, alpha==255
            raise UnsupportedError('Colour fonts not supported.')
        # get a random element to check colour mode (8/24/32 bit)
        tuple_len = len(colourset.pop())
        if tuple_len == 4:
            # RGBA
            inklevels = tuple((_c, _c, _c, 255) for _c in range(256))
        else:
            # RGB or 8-bit
            inklevels = tuple((_c,) * tuple_len for _c in range(256))
        return inklevels
    else:
        # 2-colour image
        if not isinstance(background, str):
            # background provided
            paper = background
        elif background in ('most-common', 'least-common'):
            colourfreq = Counter(colours)
            if background == 'most-common':
                # most common colour in image assumed to be background colour
                paper, _ = colourfreq.most_common(1)[0]
            else:
                # least common colour in image assumed to be background colour
                paper, _ = colourfreq.most_common()[-1]
        elif background in ('darkest', 'brightest'):
            brightness = sorted((sum(_c), _c) for _c in colourset)
            if background == 'darkest':
                # darkest colour assumed to be background
                _, paper = brightness[0]
            else:
                # brightest colour assumed to be background
                _, paper = brightness[-1]
        elif background == 'top-left':
            # top-left pixel of first char assumed to be background colour
            paper = colours[0]
        else:
            raise ValueError(f'Background mode `{background}` not supported.')
        # 2 colour image - not-paper means ink
        ink = (colourset - {paper}).pop()
        return paper, ink


if Image:
    @loaders.register(
        name='image',
        patterns=(
            '*.png', '*.bmp', '*.gif', '*.tif', '*.tiff',
            '*.ppm', '*.pgm', '*.pbm', '*.pnm', '*.webp',
            '*.pcx', '*.tga', '*.jpg', '*.jpeg',
        ),
        magic=(
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
        ),
    )
    def load_image(
            infile,
            cell:Coord=None,
            margin:Coord=Coord(0, 0),
            padding:Coord=Coord(1, 1),
            scale:Coord=Coord(1, 1),
            table_size:Coord=None,
            count:int=0,
            background:str='most-common',
            first_codepoint:int=0,
            direction:str='left-to-right top-to-bottom',
            keep_empty:bool=False,
            grid:bool=False,
        ):
        """
        Extract font from image.

        grid: extract on a rigid grid (default: False)
        cell: (grid) glyph raster size X,Y. 0 or negative: calculate from table_size (default)
        margin: (grid) number of pixels in X,Y direction around glyph chart (default: 0x0)
        padding: (grid) number of pixels in X,Y direction between glyph (default: 1x1)
        table_size: (grid) number of glyphs in X, Y direction. 0 or negative means as much as fits on the axis. (default: 32x8).
        scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
        count: maximum number of glyphs to extract (within constraints of table_size). 0 or negative means extract all (default).
        background: determine background from "most-common" (default), "least-common", "brightest", "darkest", "top-left" colour
        first_codepoint: codepoint value assigned to first glyph (default: 0)
        direction: two-part string, default 'left-to-right top-to-bottom'
        keep_empty: keep empty glyphs (default: False)
        """
        with Image.open(infile) as img:
            img = img.convert('RGB')
            if grid:
                crops = extract_crops_from_grid(
                    img, table_size, cell, scale, padding, margin, direction
                )
            else:
                crops = extract_crops_from_strips(img, direction)
        if not crops:
            logging.error('Could not extract glyphs from image.')
            return Font()
        # scale
        crops = tuple(
            _crop.resize(
                (_crop.width // scale.x, _crop.height // scale.y),
                resample=Image.NEAREST,
            )
            for _crop in crops
        )
        if count > 0:
            crops = crops[:count]
        return convert_crops_to_font(
            enumerate(crops, first_codepoint), background, keep_empty
        )


    def extract_crops_from_grid(
            img, table_size, cell, scale, padding, margin, direction
        ):
        """Extract glyph crops from grid-based image."""
        # appply defaults
        if table_size is None:
            if cell is None:
                table_size = Coord(32, 8)
                cell = Coord(0, 0)
            else:
                table_size = Coord(0, 0)
        elif cell is None:
            cell = Coord(0, 0)
        (
            cell, step_x, step_y, table_size_x, table_size_y
        ) = determine_grid_geometry(
            img.width, img.height, table_size, cell, scale, padding, margin,
        )
        traverse = grid_traverser(table_size_x, table_size_y, direction)
        # extract sub-images
        crops = tuple(
            img.crop((
                min(img.width, margin.x + _col*step_x),
                max(0, img.height - (margin.y + _row*step_y + cell.y*scale.y)),
                min(img.width, margin.x + _col*step_x + cell.x*scale.x),
                max(0, img.height - (margin.y + _row*step_y)),
            ))
            for _row, _col in traverse
        )
        # three-colour mode - proportional width encoded with border colour
        colourset = set(img.getdata())
        if len(colourset) >= 3:
            # get border/padding colour
            border = _get_border_colour(img, cell, margin, padding)
            # clip off border colour from cells
            crops = tuple(_crop_border(_crop, border) for _crop in crops)
        return crops


    def determine_grid_geometry(
            width, height, table_size, cell, scale, padding, margin,
        ):
        """Find cell, step, row and column sizes."""
        # determine defaults & whether to work with cell-size or table size
        # maximum number of cells that fits
        cell_x, cell_y = cell
        if cell.x <= 0:
            if table_size.x <= 0:
                raise ValueError('Either cell or table size must be specified.')
            cell_x = ceildiv(width, table_size.x*scale.x) - padding.x
        if cell.y <= 0:
            if table_size.y <= 0:
                raise ValueError('Either cell or table size must be specified.')
            cell_y = ceildiv(height, table_size.y*scale.y) - padding.y
        if not cell_x or not cell_y:
            raise ValueError('Empty cell. Please specify larger cell size or smaller table size.')
        logging.debug('Cell size %dx%d', cell_x, cell_y)
        cell = Coord(cell_x, cell_y)
        # work out image geometry
        step_x = cell.x * scale.x + padding.x
        step_y = cell.y * scale.y + padding.y
        table_size_x, table_size_y = table_size
        if table_size.x <= 0:
            table_size_x = ceildiv(width - margin.x, step_x)
        if table_size.y <= 0:
            table_size_y = ceildiv(height - margin.y, step_y)
        return cell, step_x, step_y, table_size_x, table_size_y


    def convert_crops_to_font(enumerated_crops, background, keep_empty):
        """Convert list of glyph images to font."""
        enumerated_crops = tuple(enumerated_crops)
        # get pixels
        _, crops = tuple(zip(*enumerated_crops))
        inklevels = _identify_colours(crops, background)
        # convert to glyphs, set codepoints
        glyphs = tuple(
            Glyph.from_vector(
                tuple(_crop.getdata()),
                stride=_crop.width,
                inklevels=inklevels,
                codepoint=_index,
            )
            for _index, _crop in enumerated_crops
        )
        # drop empty glyphs
        if not keep_empty:
            glyphs = tuple(_g for _g in glyphs if _g.height and _g.width)
        return Font(glyphs)

    def _get_border_colour(img, cell, margin, padding):
        """Get border/padding colour."""
        if margin.x or margin.y:
            return img.getpixel((0, 0))
        elif padding.x:
            return img.getpixel((cell.x, 0))
        elif padding.y:
            return img.getpixel((0, cell.y))
        # can't determine border colour without padding or margin
        return None

    def _identify_colours(crops, background):
        """Identify ink levels from cells."""
        crops = (tuple(_crop.getdata()) for _crop in crops)
        colours = sum(crops, ())
        return identify_inklevels(colours, background)

    def _crop_border(image, border):
        """Remove border area from image."""
        if border is None:
            return image
        while image.width:
            right_colours = image.crop((
                image.width-1, 0, image.width, image.height
            )).getcolors()
            if len(right_colours) == 1 and right_colours[0][1] == border:
                image = image.crop((0, 0, image.width-1, image.height))
            else:
                break
        return image


    def extract_crops_from_strips(img, direction):
        """Extract glyph crops from strip-based image."""
        # we extract left-to-right or top-to-bottom
        glyph_dir, _, line_dir = direction.lower().partition(' ')
        glyph_dir = glyph_dir[:1] or 'l'
        line_dir = line_dir[:1] or 't'
        vertical = glyph_dir in ('t', 'b')
        strips, border = chop_strips(img, border=None, vertical=not vertical)
        if glyph_dir in ('r', 'b'):
            strips = strips[::-1]
        crops = []
        for strip in strips:
            strip_crops, _ = chop_strips(strip, border, vertical=vertical)
            if line_dir in ('r', 'b'):
                crops = crops[::-1]
            crops.extend(strip_crops)
        return crops


    def chop_strips(img, border, vertical):
        """Slice up image into strips by border colour."""
        if vertical:
            scan_range = range(img.height)
            def _get_slice(start, stop):
                return (0, start, img.width, stop)
        else:
            scan_range = range(img.width)
            def _get_slice(start, stop):
                return (start, 0, stop, img.height)
        strips = []
        last_line = 0
        for i_line in scan_range:
            line = img.crop(_get_slice(i_line, i_line+1))
            colours = line.getcolors()
            # identify border colour
            # the first full row of one colour is deemed to be border
            if len(colours) == 1 and border is None or colours[0][1] == border:
                # found full row of one colour
                if border is None:
                    border = colours[0][1]
                if i_line - last_line:
                    strip = img.crop(_get_slice(last_line, i_line))
                    strips.append(strip)
                last_line = i_line + 1
        if i_line + 1 - last_line:
            strip = img.crop(_get_slice(last_line, i_line+1))
            strips.append(strip)
        return strips, border


    ###########################################################################

    @savers.register(linked=load_image)
    def save_image(
            fonts, outfile, *,
            image_format:str='png',
            glyphs_per_line:int=32,
            margin:Coord=Coord(0, 0),
            padding:Coord=Coord(1, 1),
            scale:Coord=Coord(1, 1),
            direction:str='left-to-right top-to-bottom',
            border:RGB=RGB(32, 32, 32),
            paper:RGB=RGB(0, 0, 0),
            ink:RGB=RGB(255, 255, 255),
            codepoint_range:tuple[Codepoint]=None,
            grid_positioning:bool=True,
        ):
        """
        Export font to grid-based image.

        image_format: image file format (default: png)
        glyphs_per_line: number of glyphs per line in glyph chart (default: 32)
        margin: number of pixels in X,Y direction around glyph grid (default: 0x0)
        padding: number of pixels in X,Y direction between glyphs (default: 1x1)
        scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
        direction: two-part string, default 'left-to-right top-to-bottom'
        paper: background colour R,G,B 0--255 (default: 0,0,0)
        ink: full-intensity foreground colour R,G,B 0--255 (default: 255,255,255)
        border: border colour R,G,B 0--255 (default 32,32,32)
        codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
        grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: false)
        """
        glyph_map = create_chart(
            fonts,
            glyphs_per_line=glyphs_per_line,
            margin=margin,
            padding=padding,
            scale=scale,
            direction=direction,
            codepoint_range=codepoint_range,
            grid_positioning=grid_positioning,
        )
        img, = glyph_map.to_images(
            border=border, paper=paper, ink=ink, transparent=False
        )
        try:
            img.save(outfile, format=image_format or Path(outfile).suffix[1:])
        except (KeyError, ValueError, TypeError):
            img.save(outfile, format=DEFAULT_IMAGE_FORMAT)


    ###########################################################################
    # image-set

    @container_loaders.register(name='imageset')
    def load_imageset(
            location,
            background:str='most-common',
            prefix:str='',
            base:int=16,
        ):
        """
        Extract font from per-glyph images.

        background: determine background from "most-common" (default), "least-common", "brightest", "darkest", "top-left" colour
        prefix: part of the image file name before the codepoint
        base: radix of numerals in file name representing code point
        """
        def _load_image_glyph(stream):
            crop = Image.open(stream)
            crop = crop.convert('RGB')
            cp = int(Path(stream.name).stem.removeprefix(prefix), base)
            # return codepoint, image pair to be parsed by convert_crops_to_font
            return (cp, crop)

        crops = loop_load(location, _load_image_glyph)
        return convert_crops_to_font(crops, background, keep_empty=True)


    @container_savers.register(linked=load_imageset)
    def save_imageset(
            fonts, location,
            prefix:str='',
            image_format:str='png',
            paper:RGB=(0, 0, 0),
            ink:RGB=(255, 255, 255),
        ):
        """
        Export font to per-glyph images.

        prefix: part of the image file name before the codepoint
        image_format: image file format (default: png)
        paper: background colour R,G,B 0--255 (default: 0,0,0)
        ink: foreground colour R,G,B 0--255 (default: 255,255,255)
        """
        def _save_image_glyph(glyph, imgfile):
            img = glyph_to_image(glyph, paper, ink)
            try:
                img.save(imgfile, format=image_format or Path(imgfile).suffix[1:])
            except (KeyError, ValueError, TypeError):
                img.save(imgfile, format=DEFAULT_IMAGE_FORMAT)

        loop_save(
            fonts, location, prefix,
            suffix=image_format, save_func=_save_image_glyph
        )
