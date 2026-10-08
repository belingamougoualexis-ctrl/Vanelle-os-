from fastapi import FastAPI, HTTPException
from .models import ProjectCreate
from .store import create, load

app = FastAPI(title="KINOA API", version="0.1.0")

@app.get("/health")
def health():
    return {"status":"ok","product":"KINOA","simulation":False}

@app.post("/api/projects", status_code=201)
def create_project(req: ProjectCreate):
    return create(req)

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    try: return load(project_id)
    except FileNotFoundError: raise HTTPException(404, "Project not found")

@app.post("/api/projects/{project_id}/resume")
def resume_project(project_id: str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404, "Project not found")
    return {"project_id":p.id,"resumable":True,"checkpoint":p.checkpoint,"progress":p.progress}
