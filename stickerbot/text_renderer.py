"""Unicode watermark layout with Fontconfig fallback shared by images and videos."""
from io import BytesIO
import re

import cairocffi as cairo
import pangocffi as pango
import pangocairocffi
from PIL import Image

DEFAULT_COLOR = '#FFFFFF'


def normalize_color(value: str) -> str:
    value = (value or '').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?', value):
        raise ValueError('Couleur invalide : utilise un code comme #FF0000.')
    return value.upper()


def render_text(text: str, max_width: int, max_height: int, size: int, color: str) -> Image.Image:
    """Render shaped multi-script text without altering decorative Unicode letters."""
    normalized = normalize_color(color)
    alpha = int(normalized[7:9], 16) / 255 if len(normalized) == 9 else 1
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max_width, max_height)
    ctx = cairo.Context(surface)
    layout = pangocairocffi.create_layout(ctx)
    layout.text = text
    description = pango.FontDescription()
    description.family = 'Noto Sans, Noto Sans Math, DejaVu Sans, sans-serif'
    for font_size in range(size, 3, -1):
        description.set_absolute_size(pango.units_from_double(font_size))
        layout.font_description = description
        ink, _ = layout.get_extents()
        width = pango.units_to_double(ink.width)
        height = pango.units_to_double(ink.height)
        if width <= max_width - 4 and height <= max_height - 4:
            break
    else:
        raise ValueError('Écriture trop longue : choisis un texte plus court.')
    if pango.pango.pango_layout_get_unknown_glyphs_count(layout.pointer):
        raise ValueError('Cette écriture contient un caractère sans police disponible. Essaie une autre écriture.')
    ctx.move_to(2 - pango.units_to_double(ink.x), 2 - pango.units_to_double(ink.y))
    pangocairocffi.layout_path(ctx, layout)
    ctx.set_source_rgba(0, 0, 0, 0.25 * alpha)
    ctx.set_line_width(1.5)
    ctx.stroke_preserve()
    rgb = tuple(int(normalized[i:i + 2], 16) / 255 for i in (1, 3, 5))
    ctx.set_source_rgba(*rgb, 0.45 * alpha)
    ctx.fill()
    buffer = BytesIO()
    surface.write_to_png(buffer)
    return Image.open(BytesIO(buffer.getvalue())).convert('RGBA').crop((0, 0, int(width + 4.999), int(height + 4.999)))
