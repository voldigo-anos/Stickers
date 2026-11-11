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


def render_text_frames(label, width, height, x, y, fps=15, seconds=3):
    """Animate slices of the already-shaped label; Unicode layout stays intact.

    Complete text, disappearance, shuffled falling letters, then complete text.
    The final baseline and left edge never move.
    """
    import random
    frames = []
    # Split at transparent columns so connected scripts keep their shaping.
    alpha = label.getchannel('A')
    spans, start = [], None
    for column in range(label.width):
        occupied = alpha.crop((column, 0, column + 1, label.height)).getbbox() is not None
        if occupied and start is None:
            start = column
        elif not occupied and start is not None:
            spans.append((start, column))
            start = None
    if start is not None:
        spans.append((start, label.width))
    order = list(range(len(spans)))
    random.Random(42).shuffle(order)
    ranks = {index: rank for rank, index in enumerate(order)}
    for number in range(fps * seconds):
        t = number / fps
        frame = Image.new('RGBA', (width, height))
        if t < .45 or t >= 2.4:
            frame.alpha_composite(label, (x, y))
        elif t >= .7:
            for index, (left, right) in enumerate(spans):
                begin = .7 + ranks[index] / max(1, len(spans)) * 1.05
                progress = min(1., max(0., (t - begin) / .5))
                if progress <= 0:
                    continue
                tile = label.crop((left, 0, right, label.height))
                tile.putalpha(tile.getchannel('A').point(lambda value: int(value * progress)))
                offset = round((1 - progress) ** 2 * min(y, label.height * 2))
                frame.alpha_composite(tile, (x + left, y - offset))
        frames.append(frame)
    return frames
