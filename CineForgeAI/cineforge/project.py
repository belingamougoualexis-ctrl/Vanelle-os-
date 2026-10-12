import json
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_VERSION = 1

def new_project(title="Mon premier film", premise=""):
    now = datetime.now(timezone.utc).isoformat()
    return {"schema_version": SCHEMA_VERSION, "title": title, "premise": premise, "genre": "Drame",
            "characters": [], "scenes": [], "created_at": now, "updated_at": now}

def save_project(project, path):
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)

def load_project(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("scenes"), list):
        raise ValueError("Format de projet CineForge non valide ou non pris en charge.")
    return data
