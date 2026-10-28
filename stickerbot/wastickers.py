"""Construction des fichiers .wastickers pour l'import vers WhatsApp."""

import math
import zipfile
from io import BytesIO
from typing import List, Tuple

from PIL import Image
from wa_validation import validate_webp, validate_tray

TRAY_ICON_SIZE = 96
TRAY_ICON_MAX_BYTES = 50 * 1024
TITLE_MAX_LEN = 128
AUTHOR_MAX_LEN = 128
STICKERS_PER_FILE = 30


def build_tray_icon_png(first_sticker_webp: bytes) -> bytes:
    im = Image.open(BytesIO(first_sticker_webp)).convert('RGBA')
    size = TRAY_ICON_SIZE
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    scale = min(size / im.width, size / im.height)
    new_w, new_h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas.paste(im, ((size - new_w) // 2, (size - new_h) // 2), im)

    buf = BytesIO()
    canvas.save(buf, 'PNG', optimize=True)
    data = buf.getvalue()
    if len(data) > TRAY_ICON_MAX_BYTES:
        buf = BytesIO()
        canvas.convert('P', palette=Image.ADAPTIVE, colors=128).save(buf, 'PNG', optimize=True)
        data = buf.getvalue()
    validate_tray(data)
    return data


def _slugify(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum():
            keep.append(ch)
        elif ch in (' ', '_', '-'):
            keep.append('_')
    slug = ''.join(keep).strip('_')
    return slug[:60] if slug else 'pack'


def files_count_for(total: int, batch_size: int = STICKERS_PER_FILE) -> int:
    return max(1, math.ceil(total / batch_size))


def build_wastickers_files(
    title: str,
    author: str,
    stickers_webp: List[bytes],
    tray_icon_png: bytes,
    batch_size: int = STICKERS_PER_FILE,
) -> List[Tuple[str, BytesIO]]:
    if not stickers_webp:
        raise ValueError('aucun sticker a empaqueter')
    if not 3 <= batch_size <= 30:
        raise ValueError('Un fichier WhatsApp doit contenir de 3 à 30 stickers.')
    validate_tray(tray_icon_png)

    # WhatsApp refuse un pack melangeant animes et statiques, et exige 3 stickers min
    animated, static = [], []
    for webp in stickers_webp:
        (animated if validate_webp(webp) else static).append(webp)
    batches = []
    for group in (static, animated):
        remaining = list(group)
        while remaining:
            take = min(batch_size, len(remaining))
            if 0 < len(remaining) - take < 3 and take >= 6:
                take -= 3 - (len(remaining) - take)
            batch, remaining = remaining[:take], remaining[take:]
            # A single-media conversion still produces an importable pack.
            while len(batch) < 3:
                batch = batch + batch[:3 - len(batch)]
            batches.append(batch)
    total_files = len(batches)

    safe_title = (title or 'Pack').strip()[:TITLE_MAX_LEN] or 'Pack'
    safe_author = (author or 'Stickers Bot').strip()[:AUTHOR_MAX_LEN] or 'Stickers Bot'

    results = []
    for part_index, batch in enumerate(batches, start=1):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            suffix = '' if total_files == 1 else f' ({part_index}/{total_files})'
            part_title = safe_title[:TITLE_MAX_LEN - len(suffix)] + suffix
            zf.writestr('title.txt', part_title)
            zf.writestr('author.txt', safe_author)
            zf.writestr('icon.png', build_tray_icon_png(batch[0]))
            for i, webp_bytes in enumerate(batch, start=1):
                zf.writestr(f'{i:02d}.webp', webp_bytes)
        buf.seek(0)

        base_name = _slugify(safe_title)
        filename = f'{base_name}.wastickers' if total_files == 1 else f'{base_name}_{part_index}.wastickers'
        results.append((filename, buf))

    return results
