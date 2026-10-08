from pathlib import Path
import subprocess
from app.media import ffmpeg_available, ffprobe_available, assemble_videos, validate_media
from app.audio import mux_audio

def test_media_tools_are_reported():
    assert ffmpeg_available() is True
    assert ffprobe_available() is True

def test_real_ffmpeg_assembly_and_probe(tmp_path: Path):
    a=tmp_path/"a.mp4"; b=tmp_path/"b.mp4"; out=tmp_path/"final.mp4"
    for target, freq in ((a,"440"),(b,"660")):
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi",
                        "-i",f"color=c=black:s=320x180:r=24","-t","0.4","-an",str(target)],check=True)
    result=assemble_videos([a,b],out,project_root=tmp_path,fps=24,width=320,height=180)
    assert result["qa"]["valid"] is True
    assert out.exists() and out.stat().st_size > 0
    qa=validate_media(out,expected_fps=24)
    assert qa["valid"] is True
    assert qa["duration_seconds"] > 0.6


def test_assembly_rejects_invalid_input(tmp_path: Path):
    import pytest
    from app.media import assemble_videos
    bad=tmp_path/"bad.mp4"; bad.write_bytes(b"not media")
    with pytest.raises(Exception):
        assemble_videos([bad],tmp_path/"out.mp4",project_root=tmp_path)


def test_real_audio_mux(tmp_path: Path):
    video=tmp_path/"video.mp4"; audio=tmp_path/"audio.wav"; out=tmp_path/"muxed.mp4"
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i","color=c=black:s=320x180:r=24","-t","0.5","-an",str(video)],check=True)
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i","sine=frequency=440:duration=0.5","-c:a","pcm_s16le",str(audio)],check=True)
    result=mux_audio(video,audio,out,project_root=tmp_path)
    assert out.exists() and out.stat().st_size > 0
    qa=validate_media(out,expected_fps=24)
    assert qa["valid"] is True


def test_project_audio_assembly_imports_real_mux(tmp_path: Path):
    from app.assembly import assemble_project
    video=tmp_path/"scene.mp4"; audio=tmp_path/"audio.wav"
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i","color=c=black:s=320x180:r=24","-t","0.5","-an",str(video)],check=True)
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i","sine=frequency=440:duration=0.5","-c:a","pcm_s16le",str(audio)],check=True)
    result=assemble_project(tmp_path,[video],"exports/final.mp4",audio_file=audio)
    assert Path(result["output"]).exists()
    assert result["pipeline"]["audio"]=="muxed"
    assert validate_media(result["output"])["valid"] is True
