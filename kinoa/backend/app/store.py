from pathlib import Path
import json, uuid
from .models import Project, ProjectCreate

ROOT = Path(__file__).resolve().parents[1] / "data"
ROOT.mkdir(parents=True, exist_ok=True)

def _path(pid: str) -> Path:
    safe = "".join(c for c in pid if c.isalnum() or c in "-_")
    return ROOT / safe / "project.json"

def save(p: Project) -> Project:
    path = _path(p.id); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp"); tmp.write_text(p.model_dump_json(indent=2), encoding="utf-8"); tmp.replace(path)
    return p

def create(req: ProjectCreate) -> Project:
    pid = uuid.uuid4().hex
    title = req.title or "Untitled Film"
    p = Project(id=pid, title=title, film_bible={
        "concept": req.idea, "genre": req.genre, "tone": req.tone, "language": req.language,
        "world": {"era": req.era, "mood": req.mood}, "visual": {"style": req.visual_style, "realism": req.realism},
        "continuity_rules": []
    })
    return save(p)

def load(pid: str) -> Project:
    path = _path(pid)
    if not path.exists(): raise FileNotFoundError(pid)
    return Project.model_validate_json(path.read_text(encoding="utf-8"))
