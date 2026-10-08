from app.media import ffmpeg_available, ffprobe_available

def test_media_tools_are_reported():
    assert isinstance(ffmpeg_available(), bool)
    assert isinstance(ffprobe_available(), bool)
