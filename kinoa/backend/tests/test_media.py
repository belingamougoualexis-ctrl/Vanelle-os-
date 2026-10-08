from pathlib import Path
import subprocess
from app.media import ffmpeg_available, ffprobe_available, assemble_videos, validate_media

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
