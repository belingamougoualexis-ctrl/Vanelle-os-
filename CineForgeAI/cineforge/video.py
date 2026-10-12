import shutil
import subprocess
from pathlib import Path

def ffmpeg_available():
    return shutil.which("ffmpeg") is not None

def assemble_mp4(clips, output_path):
    if not clips:
        raise ValueError("Aucun clip généré à assembler.")
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg est introuvable. Installe-le et ajoute-le au PATH.")
    missing = [str(p) for p in clips if not Path(p).is_file() or Path(p).stat().st_size == 0]
    if missing:
        raise FileNotFoundError("Clips manquants ou vides : " + ", ".join(missing))
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = out.parent / (out.stem + "_concat.txt")
    manifest.write_text("\n".join("file '" + str(Path(p).resolve()).replace("\\","/").replace("'","'\\''") + "'" for p in clips), encoding="utf-8")
    proc = subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(manifest),"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(out)],capture_output=True,text=True,timeout=3600)
    if proc.returncode or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("Échec FFmpeg : " + (proc.stderr[-2000:] if proc.stderr else "sortie absente"))
    return out
