from __future__ import annotations
from pathlib import Path
from typing import Any
from .media import assemble_videos

def assemble_project(project_root: str | Path, scene_files: list[str | Path], output: str | Path,
                     fps: int=24, width: int=1280, height: int=720,
                     intro_file: str | Path | None=None) -> dict[str,Any]:
    root=Path(project_root).resolve()
    files=[Path(x) for x in scene_files]
    if intro_file is not None:
        files=[Path(intro_file),*files]
    result=assemble_videos(files, root / output, project_root=root, fps=fps, width=width, height=height)
    result["pipeline"]={"intro_included":intro_file is not None,"audio":"not configured","qa":"ffprobe"}
    return result
