from __future__ import annotations
from pathlib import Path
from typing import Any
from .media import assemble_videos

def assemble_project(project_root: str | Path, scene_files: list[str | Path], output: str | Path,
                     fps: int=24, width: int=1280, height: int=720) -> dict[str,Any]:
    root=Path(project_root).resolve()
    return assemble_videos(scene_files, root / output, project_root=root, fps=fps, width=width, height=height)
