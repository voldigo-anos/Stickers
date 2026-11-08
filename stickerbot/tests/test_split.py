import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import converter


def test_segment_starts_cover_whole_video():
    assert converter.segment_starts(3600) == [i * 3.0 for i in range(1200)]
    assert converter.segment_starts(10) == [0, 3, 6, 9]
    assert converter.segment_starts(9.2) == [0, 3, 6]  # 0.2 s restant ignore


def test_encode_segment_from_middle():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        'testsrc=size=640x360:rate=30', '-t', '10', src], check=True)
        assert 9.5 < converter.video_duration(src) < 10.5
        out = converter.encode_segment(tmp, '.mp4', 6.0, converter.SHAPE_ROUNDED, 'test', '#FFFFFF')
        assert out[:4] == b'\x1a\x45\xdf\xa3' and len(out) <= converter.VIDEO_MAX_BYTES
        dst = os.path.join(tmp, 'o.webm'); open(dst, 'wb').write(out)
        assert converter.video_duration(dst) <= 3.05
