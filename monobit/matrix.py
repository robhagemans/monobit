"""
monobit.matrix - matrix utilities

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

try:
    from PIL import Image
except ImportError:
    Image = None



###################################################################################################
# matrix operations

def create(width, height, fill=0):
    """Create a matrix in list format."""
    return [
        [fill for _ in range(width)]
        for _ in range(height)
    ]

def scale(matrix, scale_x, scale_y):
    """Scale a matrix in list format."""
    return [
        [_item  for _item in _row for _ in range(scale_x)]
        for _row in matrix for _ in range(scale_y)
    ]

def rotate(matrix, quarter_turns=1):
    """Scale a matrix in list format."""
    for turn in range(quarter_turns):
        matrix = mirror(transpose(matrix))
    return matrix

def transpose(matrix):
    """Transpose a matrix."""
    return list(zip(*matrix))

def mirror(matrix):
    """Mirror a matrix."""
    return [reversed(_row) for _row in matrix]


def blit(matrix, canvas, grid_x, grid_y, operator=max):
    """Draw a matrix onto a canvas (leaving exising ink in place, depending on operator)."""
    if not matrix or not canvas:
        return canvas
    matrix_height = len(matrix)
    canvas_height = len(canvas)
    canvas_width = len(canvas[0])
    for work_y in range(matrix_height):
        y_index = grid_y - work_y - 1
        if 0 <= y_index < canvas_height:
            row = canvas[y_index]
            for work_x, ink in enumerate(matrix[matrix_height - work_y - 1]):
                if 0 <= grid_x + work_x < canvas_width:
                    row[grid_x + work_x] = operator(ink, row[grid_x + work_x])
    return canvas


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

def to_text(matrix, *, border=' ', paper='-', ink='@', line_break='\n'):
    """Convert matrix to text."""
    colourdict = {-1: border, 0: paper, 1: ink}
    return line_break.join(''.join(colourdict[_pix] for _pix in _row) for _row in matrix)
