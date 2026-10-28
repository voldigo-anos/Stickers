"""Validate decoded exports against WhatsApp's StickerPackValidator rules."""
from io import BytesIO

from PIL import Image

STATIC_MAX_BYTES = 100 * 1024
ANIMATED_MAX_BYTES = 500 * 1024
TRAY_MAX_BYTES = 50 * 1024


def validate_webp(data: bytes) -> bool:
    """Return the decoded animation flag, or reject an invalid final sticker."""
    with Image.open(BytesIO(data)) as im:
        if im.format != 'WEBP' or im.size != (512, 512):
            raise ValueError('Le sticker doit être un WebP de 512 × 512 pixels.')
        animated = im.n_frames > 1
        limit = ANIMATED_MAX_BYTES if animated else STATIC_MAX_BYTES
        if len(data) > limit:
            raise ValueError(f'Sticker trop lourd : maximum {limit // 1024} Ko.')
        duration = 0
        for index in range(im.n_frames):
            im.seek(index)
            im.load()
            if animated:
                frame_duration = im.info.get('duration', 0)
                if frame_duration < 8:
                    raise ValueError('Animation invalide : chaque image doit durer au moins 8 ms.')
                duration += frame_duration
        if animated and duration > 10000:
            raise ValueError('Animation trop longue : maximum 10 secondes.')
        return animated


def validate_tray(data: bytes):
    with Image.open(BytesIO(data)) as im:
        if im.format != 'PNG' or im.size != (96, 96) or len(data) > TRAY_MAX_BYTES:
            raise ValueError('Icône invalide : PNG 96 × 96, maximum 50 Ko.')
        im.load()