from __future__ import annotations
import json
import shutil
import subprocess
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
            if d and round(float(n)/float(d)) != expected_fps:
                errors.append("Unexpected FPS")
    duration=float(info.get("format",{}).get("duration") or 0)
    if duration <= 0:
        errors.append("Invalid duration")
    return {"valid":not errors,"errors":errors,"duration_seconds":duration,"codec":video.get("codec_name"),"width":video.get("width"),"height":video.get("height")}
