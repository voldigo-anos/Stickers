"""Run with: PYTHONPATH=stickerbot python -m unittest discover -s stickerbot/tests."""
import asyncio
import os
import subprocess
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image
from telegram import Update

import bot
import converter
import keyboards
import themes
import wastickers
from wa_validation import validate_webp, validate_tray


def image_bytes(color=(170, 25, 60), size=(512, 512), fmt='PNG'):
    out = BytesIO()
    Image.new('RGB', size, color).save(out, fmt)
    return out.getvalue()


def animation_bytes(durations=(100, 100), size=(512, 512)):
    frames = [Image.new('RGBA', size, (index * 70, 40, 200, 255)) for index in range(len(durations))]
    out = BytesIO()
    frames[0].save(out, 'WEBP', save_all=True, append_images=frames[1:], duration=list(durations), loop=0)
    return out.getvalue()


class ExportRules(unittest.TestCase):
    def test_static_dimension_rule(self):
        with self.assertRaises(ValueError):
            validate_webp(image_bytes(size=(511, 512), fmt='WEBP'))
        output = converter.to_wa_webp(image_bytes(size=(900, 300)), '.png')
        self.assertEqual(Image.open(BytesIO(output)).size, (512, 512))

    def test_static_100_kib_limit(self):
        valid = image_bytes(fmt='WEBP')
        with self.assertRaises(ValueError):
            validate_webp(valid + bytes(102401 - len(valid)))
        noisy = Image.effect_noise((512, 512), 100).convert('RGB')
        buffer = BytesIO()
        noisy.save(buffer, 'PNG')
        self.assertLessEqual(len(converter.to_wa_webp(buffer.getvalue(), '.png')), 100 * 1024)

    def test_animation_500_kib_limit(self):
        valid = animation_bytes()
        with self.assertRaises(ValueError):
            validate_webp(valid + bytes(512001 - len(valid)))
        self.assertLessEqual(len(converter.to_wa_webp(valid, '.webp')), 500 * 1024)

    def test_animation_ten_second_limit(self):
        with self.assertRaises(ValueError):
            validate_webp(animation_bytes((6000, 6000)))

    def test_animation_eight_ms_minimum(self):
        with self.assertRaises(ValueError):
            validate_webp(animation_bytes((7, 100)))
        self.assertTrue(validate_webp(animation_bytes((8, 100))))

    def test_tray_rules(self):
        tray = wastickers.build_tray_icon_png(image_bytes(fmt='WEBP'))
        validate_tray(tray)
        self.assertEqual(Image.open(BytesIO(tray)).size, (96, 96))
        self.assertLessEqual(len(tray), 50 * 1024)
        with self.assertRaises(ValueError):
            validate_tray(image_bytes(size=(95, 96)))
        with self.assertRaises(ValueError):
            validate_tray(tray + bytes(51201 - len(tray)))

    def test_pack_minimum_maximum_and_separate_animation(self):
        static = image_bytes(fmt='WEBP')
        animated = animation_bytes()
        tray = wastickers.build_tray_icon_png(static)
        files = wastickers.build_wastickers_files('Test', 'Bot', [static] * 31 + [animated], tray)
        self.assertEqual(len(files), 3)
        counts = []
        for _, buffer in files:
            with zipfile.ZipFile(buffer) as archive:
                values = [archive.read(n) for n in archive.namelist() if n.endswith('.webp')]
                counts.append(len(values))
                self.assertGreaterEqual(len(values), 3)
                self.assertLessEqual(len(values), 30)
                self.assertEqual(len({validate_webp(v) for v in values}), 1)
                validate_tray(archive.read('icon.png'))
        self.assertEqual(counts, [28, 3, 3])
        with self.assertRaises(ValueError):
            wastickers.build_wastickers_files('Test', 'Bot', [static], tray, 31)

    def test_archive_rejects_invalid_sticker(self):
        valid = image_bytes(fmt='WEBP')
        with self.assertRaises(ValueError):
            wastickers.build_wastickers_files('Test', 'Bot', [image_bytes(size=(400, 512), fmt='WEBP')], wastickers.build_tray_icon_png(valid))

    def test_theme_android_parser_wallpaper_and_photo_palette(self):
        photo = image_bytes((185, 30, 65), (720, 900))
        output = themes.build_attheme(photo)
        # Match Theme.java's parser: stop at WPS, offset is after its newline.
        offset = 0
        keys = {}
        for line in output.split(b'\n'):
            offset += len(line) + 1
            if line.startswith(b'WPS'):
                break
            key, value = line.decode().split('=', 1)
            keys[key] = int(value)
        wallpaper = Image.open(BytesIO(output[offset:]))
        self.assertEqual(wallpaper.size, (720, 900))
        pixel = wallpaper.convert('RGB').getpixel((200, 200))
        self.assertLess(sum(abs(pixel[i] - (185, 30, 65)[i]) for i in range(3)), 10)
        self.assertTrue(output.endswith(b'\nWPE\n'))
        other = themes._theme_keys(themes.extract_palette(image_bytes((20, 150, 210))))
        for key in ('windowBackgroundWhite', 'chat_inBubble', 'chat_outBubble', 'chat_inVoiceSeekbarFill', 'actionBarDefault'):
            self.assertNotEqual(keys[key], -1)
            self.assertNotEqual(keys[key], other[key])

    def test_actual_video_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'video.mp4'
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                            '-i', 'testsrc2=size=640x360:rate=15', '-t', '1', '-c:v', 'libx264', str(src)], check=True)
            output = converter.to_wa_webp(src.read_bytes(), '.mp4')
            self.assertTrue(validate_webp(output))


class ConversationFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.message = AsyncMock()
        self.context = SimpleNamespace(user_data={'theme_mode': True}, bot=SimpleNamespace(
            username='example_bot', get_sticker_set=AsyncMock(return_value=SimpleNamespace(title='Source', stickers=[1, 2, 3])),
            send_document=AsyncMock(), send_message=AsyncMock()), application=SimpleNamespace(create_task=self.schedule))
        self.tasks = []
        self.user = SimpleNamespace(id=123, username='test', first_name='Test')
        self.update = SimpleNamespace(effective_user=self.user, effective_chat=SimpleNamespace(id=123), effective_message=self.message)

    def schedule(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    async def test_button_sticker_choice_conversion_and_archive_readback(self):
        with patch.object(bot.db, 'save_user'), patch.object(bot.db, 'is_banned', return_value=False):
            self.message.text = keyboards.BTN_CONVERT
            await bot.on_text(self.update, self.context)
            self.assertNotIn('theme_mode', self.context.user_data)
            real_update = Update.de_json({'update_id': 1, 'message': {'message_id': 1, 'date': 1,
                'chat': {'id': 123, 'type': 'private'}, 'from': {'id': 123, 'is_bot': False, 'first_name': 'Test'},
                'sticker': {'file_id': 'file', 'file_unique_id': 'unique', 'width': 512, 'height': 512,
                            'is_animated': False, 'is_video': False, 'type': 'regular', 'set_name': 'x' * 100}}}, None)
            self.update.effective_message = real_update.message
            with patch.object(bot, 'reply', new_callable=AsyncMock) as replies:
                await bot.on_media(self.update, self.context)
            self.assertEqual(self.context.user_data['wa_pending'][1], 'file')
            markup = replies.call_args.kwargs['reply_markup']
            self.assertEqual([r[0].callback_data for r in markup.inline_keyboard], ['wa_one', 'wa_pack', 'wa_no'])
            for row in markup.inline_keyboard:
                self.assertLessEqual(len(row[0].callback_data.encode()), 64)
            query = AsyncMock()
            query.data = 'wa_one'
            self.update.callback_query = query
            with patch.object(bot, 'download', new_callable=AsyncMock, return_value=image_bytes(size=(600, 400))):
                await bot.on_callback(self.update, self.context)
                await asyncio.gather(*self.tasks)
            self.assertNotIn('wa_pending', self.context.user_data)
            self.context.bot.send_document.assert_awaited_once()
            archive_buffer = self.context.bot.send_document.call_args.kwargs['document']
            with zipfile.ZipFile(archive_buffer) as archive:
                names = [n for n in archive.namelist() if n.endswith('.webp')]
                self.assertEqual(len(names), 3)
                for name in names:
                    self.assertFalse(validate_webp(archive.read(name)))

    async def test_export_pack_failure_is_reported(self):
        with patch.object(bot, '_build_whatsapp_export', new_callable=AsyncMock, side_effect=ValueError('bad export')):
            await bot._export_whatsapp_job(self.context, 123, 'test')
        self.context.bot.send_message.assert_awaited_once()

    async def test_media_handler_matches_real_sticker(self):
        import config
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot.db, 'DB_PATH', os.path.join(tmp, 'bot.db')), patch.object(config, 'BOT_TOKEN', '123456:dummy_test_token'):
            app = bot.build_application()
        update = Update.de_json({'update_id': 1, 'message': {'message_id': 1, 'date': 1,
            'chat': {'id': 123, 'type': 'private'}, 'sticker': {'file_id': 'x', 'file_unique_id': 'y',
            'width': 512, 'height': 512, 'is_animated': False, 'is_video': False, 'type': 'regular'}}}, app.bot)
        matching = [handler for handler in app.handlers[0] if handler.check_update(update)]
        self.assertEqual(matching[0].callback, bot.on_media)


if __name__ == '__main__':
    unittest.main()