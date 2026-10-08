from __future__ import annotations
import shutil, subprocess
from pathlib import Path
from typing import Any

def _tool(name: str) -> str:
    path=shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is not installed")
    return path

def mux_audio(video: str|Path, audio: str|Path, output: str|Path, *, project_root: str|Path) -> dict[str,Any]:
    root=Path(project_root).resolve()
    v=Path(video).resolve(); a=Path(audio).resolve(); out=Path(output).resolve()
    for p in (v,a):
        if root not in p.parents or not p.is_file(): raise ValueError("Media path is outside project or missing")
    if root not in out.parents: raise ValueError("Output path escapes project directory")
    out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([_tool("ffmpeg"),"-y","-hide_banner","-loglevel","error","-i",str(v),"-i",str(a),
                    "-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-shortest",str(out)],check=True)
    return {"output":str(out),"video":str(v),"audio":str(a)}
