"""Writing rules and the selection-to-sticker flow, without a live Telegram token."""
import asyncio
from io import BytesIO
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageChops
import bot
import converter
import db
import keyboards as kb
from text_renderer import render_text


def photo():
    buf = BytesIO()
    Image.new('RGB', (720, 400), (55, 140, 105)).save(buf, 'PNG')
    return buf.getvalue()


def test_classic_is_the_original_render():
    actual = converter.watermark_layer(512, 512, 'Christus', 'cover', '#FFFFFF')
    label = render_text('Christus', 478, 102, 33, '#FFFFFF')
    expected = Image.new('RGBA', (512, 512))
    expected.alpha_composite(label, (17, 512 - 17 - label.height))
    assert actual.tobytes() == expected.tobytes()


def test_both_styles_are_lower_left_in_all_shapes():
    from text_renderer import render_text_frames
    for shape in ('original', 'square', 'cover', 'round', 'rounded'):
        layer = converter.watermark_layer(512, 512, 'Christus', shape)
        left, top, right, bottom = layer.getbbox()
        assert left < 128 and top > 350 and right < 400 and bottom <= 512
        label = layer.crop((left, top, right, bottom))
        frames = render_text_frames(label, 512, 512, left, top)
        assert frames[0].tobytes() == layer.tobytes()
        assert frames[-1].tobytes() == layer.tobytes()
        assert frames[8].getbbox() is None
        assert any(frame.getbbox() and frame.tobytes() != layer.tobytes() for frame in frames[11:35])
        for frame in frames:
            box = frame.getbbox()
            if box:
                assert box[0] >= left and box[2] <= right and box[3] <= bottom


def test_saved_style_and_legacy_default():
    with tempfile.TemporaryDirectory() as tmp, patch.object(db, 'DB_PATH', os.path.join(tmp, 'test.db')):
        db.init()
        old = db.add_pack(1, 'classic_by_bot', 'Classic')
        new = db.add_pack(1, 'animated_by_bot', 'Animated', 'cover', 'Christus', '#FFFFFF', 'animated')
        assert db.get_pack(1, 'classic_by_bot')['watermark_style'] == 'classic'
        assert db.get_pack(1, 'animated_by_bot')['watermark_style'] == 'animated'
        db.set_pack_style(old, 'rounded', 'Test', '#FFFFFF', 'animated')
        assert db.get_pack(1, 'classic_by_bot')['watermark_style'] == 'animated'
        assert new != old


def test_choice_photo_and_auto_pack_use_video():
    async def flow():
        context = SimpleNamespace(user_data={'draft': {'name': 'test_by_bot', 'title': 'Test'},
            'shape': 'rounded', 'watermark': 'Christus', 'step': bot.STEP_COLOR},
            bot=SimpleNamespace(username='bot'))
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123),
            effective_message=SimpleNamespace(text='⚪ Blanc'))
        with patch.object(bot.db, 'save_user'), patch.object(bot.db, 'is_banned', return_value=False), patch.object(bot, 'reply', new_callable=AsyncMock):
            await bot.on_text(update, context)
            assert context.user_data['step'] == bot.STEP_WM_STYLE
            update.effective_message.text = kb.BTN_WM_ANIMATED
            await bot.on_text(update, context)
            assert context.user_data['active']['watermark_style'] == 'animated'
            with patch.object(bot, 'download', new_callable=AsyncMock, return_value=photo()):
                sticker = await bot.build_input_sticker(context, 'photo', 'test_file', '.png', '🙂', context.user_data['active'])
            assert sticker.format == 'video' and len(sticker.sticker.input_file_content) <= 256 * 1024
            with patch.object(bot.pinterest, 'fetch', return_value=photo()):
                auto = await bot._auto_sticker('unused', bot.pinterest.MODE_STATIC, False, context.user_data['active'])
            assert auto.format == 'video'
    asyncio.run(flow())


def test_animated_video_segments_are_three_seconds_and_actually_move():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=green:s=640x360:r=30', '-t', '7', str(path / 'in.mp4')], check=True)
        for shape in ('cover', 'round', 'rounded', 'original', 'square'):
            result = converter.encode_segment(tmp, '.mp4', 3, shape, 'Christus', '#FFFFFF', 'animated')
            assert len(result) <= 256 * 1024
            (path / 'out.webm').write_bytes(result)
            assert 2.9 < converter.video_duration(str(path / 'out.webm')) <= 3.05
        for t, name in ((0.1, 'visible'), (.55, 'blank'), (1.4, 'falling'), (2.7, 'final')):
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-c:v', 'libvpx-vp9', '-ss', str(t), '-i',
                            str(path / 'out.webm'), '-frames:v', '1', str(path / f'{name}.png')], check=True)
        images = {name: Image.open(path / f'{name}.png').convert('RGB')
                  for name in ('visible', 'blank', 'falling', 'final')}
        assert sum(ImageChops.difference(images['visible'], images['blank']).convert('L').getdata()) > 1000
        assert sum(ImageChops.difference(images['falling'], images['blank']).convert('L').getdata()) > 100
        assert sum(ImageChops.difference(images['final'], images['blank']).convert('L').getdata()) > 1000


def test_rollover_keeps_animated_style():
    active = {'name': 'test_by_bot', 'title': 'Test', 'watermark_style': 'animated', 'shape': 'cover'}
    with patch.object(bot.db, 'get_pack_by_name', return_value=None):
        bot._roll_pack(active, 'bot')
    assert active['name'] == 'test_2_by_bot' and active['watermark_style'] == 'animated'


def test_long_video_job_forces_square_and_passes_animated_style():
    async def flow():
        active = {'name': 'test_by_bot', 'title': 'Test', 'id': None, 'created': False,
                  'shape': 'round', 'watermark': 'Christus', 'watermark_color': '#FFFFFF',
                  'watermark_style': 'animated'}
        tg_file = SimpleNamespace(download_to_drive=AsyncMock())
        context = SimpleNamespace(bot=SimpleNamespace(get_file=AsyncMock(return_value=tg_file), username='bot'))
        waiting = AsyncMock()
        with patch.object(converter, 'video_duration', return_value=6), patch.object(converter, 'encode_segment', return_value=b'test') as encode, patch.object(bot, 'push_sticker', new_callable=AsyncMock), patch.object(db, 'add_sticker'), patch.object(bot.asyncio, 'sleep', new_callable=AsyncMock):
            await bot._split_job(context, 123, 123, active, ('anim', 'file', 'unique', '.mp4', '🙂', None), waiting, {'stop': False})
        assert encode.call_count == 2
        assert [call.args[2] for call in encode.call_args_list] == [0.0, 3.0]
        assert all(call.args[3] == 'cover' and call.args[6] == 'animated' for call in encode.call_args_list)
    asyncio.run(flow())
