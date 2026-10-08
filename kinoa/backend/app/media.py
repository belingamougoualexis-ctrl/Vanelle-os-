from __future__ import annotations
import json, shutil, subprocess, tempfile
from pathlib import Path

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None

def probe_media(path: str | Path) -> dict:
    if not ffprobe_available():
        raise RuntimeError("ffprobe is not installed")
    p=subprocess.run(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def validate_media(path: str | Path, expected_fps: int | None=None) -> dict:
    info=probe_media(path)
    streams=info.get("streams",[])
    video=next((s for s in streams if s.get("codec_type")=="video"),None)
    if not video:
        return {"valid":False,"errors":["No video stream"],"streams":len(streams)}
    errors=[]
    if expected_fps:
        rate=video.get("r_frame_rate","")
        if rate and "/" in rate:
            n,d=rate.split("/",1)
            if d and round(float(n)/float(d)) != expected_fps: errors.append("Unexpected FPS")
    duration=float(info.get("format",{}).get("duration") or 0)
    if duration <= 0: errors.append("Invalid duration")
    return {"valid":not errors,"errors":errors,"duration_seconds":duration,"codec":video.get("codec_name"),"width":video.get("width"),"height":video.get("height")}

def _safe_input(path: Path, root: Path) -> Path:
    resolved=path.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("Media path escapes the allowed project directory")
    if not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    return resolved

def assemble_videos(inputs: list[str | Path], output: str | Path, *, project_root: str | Path | None=None,
                    fps: int=24, width: int=1280, height: int=720) -> dict:
    if not inputs: raise ValueError("At least one video is required")
    if not ffmpeg_available(): raise RuntimeError("ffmpeg is not installed")
    out=Path(output).resolve()
    root=Path(project_root).resolve() if project_root else out.parent.resolve()
    root.mkdir(parents=True, exist_ok=True)
    files=[_safe_input(Path(p),root) for p in inputs]
    if out.parent != root and root not in out.parents: raise ValueError("Output path escapes project directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as td:
        concat=Path(td)/"inputs.txt"
        concat.write_text("\n".join("file '"+str(p).replace("'","'\\''")+"'\n" for p in files),encoding="utf-8")
        vf=f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
        cmd=["ffmpeg","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),
             "-vf",vf,"-r",str(fps),"-c:v","libx264","-preset","veryfast","-crf","20","-an",str(out)]
        subprocess.run(cmd,check=True)
    qa=validate_media(out,expected_fps=fps)
    if not qa["valid"]: raise RuntimeError("Assembled media failed QA: "+", ".join(qa["errors"]))
    return {"output":str(out),"inputs":len(files),"qa":qa}
