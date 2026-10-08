from __future__ import annotations
from pathlib import Path
from typing import Any
from .media import assemble_videos
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
    result["output"]=str(final_output)
    result["pipeline"]={"intro_included":intro_file is not None,
                        "audio":"muxed" if audio_file is not None else "not configured",
                        "qa":"ffprobe"}
    return result
