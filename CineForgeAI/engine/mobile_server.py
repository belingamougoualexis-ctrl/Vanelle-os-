"""Authenticated local-network bridge to CineForge's real LTX-2.5 engine."""
from __future__ import annotations

import hmac
import importlib.util
import secrets
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

PROJECT_DIR = Path(__file__).resolve().parents[1]
ENGINE_SCRIPT = PROJECT_DIR / "engine" / "ltx_generate.py"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "mobile_jobs"
MODEL_ID = "Lightricks/LTX-2.5-Diffusers"
ACCESS_TOKEN = secrets.token_urlsafe(18)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("\n[CineForge] Code d'accès temporaire pour l'application Android:")
print(f"[CineForge] {ACCESS_TOKEN}")
print("[CineForge] Garde ce code privé et utilise uniquement un réseau de confiance.\n")

app = FastAPI(title="CineForge LTX Bridge", version="1.0.0")
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cineforge-video")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=12, max_length=2500)
    seconds: int = Field(default=5, ge=5, le=10)
    width: int = Field(default=768)
    height: int = Field(default=512)
    fps: Literal[24] = 24


def require_token(x_cineforge_token: str | None = Header(default=None, alias="X-CineForge-Token")) -> None:
    if not x_cineforge_token or not hmac.compare_digest(x_cineforge_token, ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Code d'accès absent ou incorrect.")


@app.get("/health")
def health() -> dict:
    torch_present = importlib.util.find_spec("torch") is not None
    device = "non disponible"
    cuda_available = False
    mps_available = False
    if torch_present:
        try:
            import torch
            cuda_available = bool(torch.cuda.is_available())
            mps_available = bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
            device = "cuda" if cuda_available else ("mps" if mps_available else "cpu")
        except Exception:
            device = "torch installé mais non initialisable"
    return {
        "status": "online",
        "model_id": MODEL_ID,
        "device": device,
        "cuda_available": cuda_available,
        "mps_available": mps_available,
        "torch_installed": torch_present,
        "model_loaded": False,
        "note": "Le modèle est chargé à la demande; aucune vidéo fictive n'est renvoyée.",
    }


def run_generation(job_id: str, payload: GenerateRequest) -> None:
    video_path = OUTPUT_DIR / f"{job_id}.mp4"
    log_path = OUTPUT_DIR / f"{job_id}.log"
    with jobs_lock:
        jobs[job_id]["status"] = "running"
    command = [
        sys.executable, str(ENGINE_SCRIPT),
        "--prompt", payload.prompt,
        "--output", str(video_path),
        "--seconds", str(payload.seconds),
        "--width", str(payload.width),
        "--height", str(payload.height),
        "--fps", str(payload.fps),
        "--model", MODEL_ID,
    ]
    try:
        if not ENGINE_SCRIPT.is_file():
            raise RuntimeError(f"Moteur introuvable: {ENGINE_SCRIPT}")
        with log_path.open("w", encoding="utf-8") as log_file:
            completed = subprocess.run(
                command,
                cwd=str(PROJECT_DIR),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=60 * 60,
                check=False,
                text=True,
            )
        if completed.returncode != 0:
            raise RuntimeError("Échec de l'inférence LTX-2.5. Consulte les journaux du moteur sur le PC.")
        if not video_path.is_file() or video_path.stat().st_size <= 1024:
            raise RuntimeError("Le moteur n'a pas produit de fichier MP4 valide.")
        with jobs_lock:
            jobs[job_id].update(status="completed", video_path=str(video_path))
    except subprocess.TimeoutExpired:
        with jobs_lock:
            jobs[job_id].update(status="failed", error="Le rendu a dépassé la limite d'une heure.")
    except Exception as exc:
        detail = str(exc)
        if log_path.is_file():
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-1800:]
                if tail:
                    detail += "\nDerniers journaux:\n" + tail
            except OSError:
                pass
        with jobs_lock:
            jobs[job_id].update(status="failed", error=detail[:4000])


@app.post("/generate", status_code=202, dependencies=[Depends(require_token)])
def create_generation(payload: GenerateRequest) -> dict:
    if (payload.width, payload.height) not in {(512, 320), (768, 512)}:
        raise HTTPException(status_code=422, detail="Résolution non prise en charge.")
    if not ENGINE_SCRIPT.is_file():
        raise HTTPException(status_code=503, detail="Le script du moteur LTX-2.5 est introuvable.")
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "error": None, "video_path": None}
    executor.submit(run_generation, job_id, payload)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_token)])
def get_job(job_id: str) -> dict:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Rendu inconnu ou serveur redémarré.")
        return {
            "job_id": job_id,
            "status": job["status"],
            "error": job.get("error") if job["status"] == "failed" else None,
        }


@app.get("/jobs/{job_id}/video", dependencies=[Depends(require_token)])
def get_video(job_id: str) -> FileResponse:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Rendu inconnu.")
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Le MP4 n'est pas encore prêt.")
        video_path = Path(job["video_path"])
    if not video_path.is_file():
        raise HTTPException(status_code=410, detail="Le fichier vidéo n'est plus disponible.")
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"CineForge_{job_id[:8]}.mp4",
    )
