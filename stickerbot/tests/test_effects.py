"""Run with: PYTHONPATH=stickerbot python -m unittest discover -s stickerbot/tests."""
import subprocess
import tempfile
import unittest
from io import BytesIO

from PIL import Image

import converter
import keyboards


def sticker(color=(200, 30, 60, 255)):
    im = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    im.paste(Image.new('RGBA', (300, 300), color), (106, 106))
    out = BytesIO()
    im.save(out, 'WEBP', lossless=True)
    return out.getvalue()


class PackEffects(unittest.TestCase):
    def test_black_and_white_static_has_no_colour(self):
        im = Image.open(BytesIO(converter.apply_effect_static(sticker(), converter.FX_BW))).convert('RGBA')
        r, g, b, _ = im.getpixel((256, 256))
        self.assertTrue(abs(r - g) <= 2 and abs(g - b) <= 2)
        self.assertEqual(im.getpixel((5, 5))[3], 0)  # transparence gardee
        self.assertEqual(im.size, (512, 512))

    def test_hd_static_keeps_size_and_transparency(self):
        data = converter.apply_effect_static(sticker(), converter.FX_HD)
        im = Image.open(BytesIO(data)).convert('RGBA')
        self.assertEqual(im.size, (512, 512))
        self.assertEqual(im.getpixel((5, 5))[3], 0)
        self.assertLessEqual(len(data), 500 * 1024)

    def test_video_effects_stay_under_telegram_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = f'{tmp}/in.webm'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            'testsrc=size=512x512:rate=30:duration=2', '-c:v', 'libvpx-vp9',
                            '-pix_fmt', 'yuva420p', src], check=True)
            raw = open(src, 'rb').read()
        for effect in (converter.FX_HD, converter.FX_BW):
            out = converter.apply_effect_video(raw, effect)
            self.assertLessEqual(len(out), converter.VIDEO_MAX_BYTES)
            self.assertEqual(out[:4], b'\x1a\x45\xdf\xa3')

    def test_pack_card_offers_retouch(self):
        datas = [b.callback_data for row in keyboards.pack_actions('abc_by_bot').inline_keyboard for b in row]
        self.assertIn('fx:abc_by_bot', datas)
        choices = [b.callback_data for row in keyboards.fx_choice().inline_keyboard for b in row]
        self.assertEqual(choices, ['fxq:hd', 'fxq:bw', 'fxq:no'])
