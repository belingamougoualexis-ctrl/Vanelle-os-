from __future__ import annotations
from pathlib import Path
from typing import Any
from .media import assemble_videos, validate_media
from .audio import mux_audio

def assemble_project(project_root: str | Path, scene_files: list[str | Path], output: str | Path,
                     fps: int=24, width: int=1280, height: int=720,
                     intro_file: str | Path | None=None,
                     audio_file: str | Path | None=None) -> dict[str,Any]:
    root=Path(project_root).resolve()
    files=[Path(x) for x in scene_files]
    if intro_file is not None:
        files=[Path(intro_file),*files]
    video_output=root / output
    result=assemble_videos(files, video_output, project_root=root, fps=fps, width=width, height=height)
    final_output=video_output
    if audio_file is not None:
        muxed=root / (video_output.stem + "_audio.mp4")
        mux_audio(video_output, audio_file, muxed, project_root=root)
        final_output=muxed
    final_qa=validate_media(final_output, expected_fps=fps)
    if not final_qa["valid"]:
        raise RuntimeError("Final export failed QA: " + ", ".join(final_qa["errors"]))
    result["output"]=str(final_output)
    result["final_qa"]=final_qa
    result["pipeline"]={"intro_included":intro_file is not None,
                        "audio":"muxed" if audio_file is not None else "not configured",
                        "qa":"ffprobe"}
    return result


def create_kinoa_original_intro(output: str | Path, *, width: int=1280, height: int=720, fps: int=24, duration: float=3.0) -> Path:
    import shutil, subprocess
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed")
    out=Path(output).resolve(); out.parent.mkdir(parents=True, exist_ok=True)
    if duration <= 0 or width < 16 or height < 16 or fps < 1:
        raise ValueError("Invalid intro parameters")
    vf=(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@1:t=fill,"
        f"drawtext=text='KINOA':fontcolor=white:fontsize={max(48,width//14)}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-20:enable='between(t,0.4,2.7)',"
        f"drawtext=text='AI FILM STUDIO':fontcolor=white:fontsize={max(20,width//42)}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+65:enable='between(t,0.8,2.7)',"
        "fade=t=in:st=0:d=0.5,fade=t=out:st=2.5:d=0.5")
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi",
                     "-i",f"color=c=black:s={width}x{height}:r={fps}","-t",str(duration),
                     "-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(out)],check=True)
    return out
