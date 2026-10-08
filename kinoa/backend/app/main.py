from fastapi import FastAPI, HTTPException
from .models import ProjectCreate, SceneCreate
from .store import create, load, save
from .hardware import detect_hardware, wan22_readiness
from .continuity import validate_scene

app = FastAPI(title="KINOA API", version="0.2.0")

@app.get("/health")
def health():
    return {"status":"ok","product":"KINOA","runtime":"real-only"}

@app.get("/api/hardware")
def hardware():
    h=detect_hardware()
    return {"hardware":h,"wan22":wan22_readiness(h)}

@app.post("/api/projects", status_code=201)
def create_project(req: ProjectCreate):
    return create(req)

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    try: return load(project_id)
    except FileNotFoundError: raise HTTPException(404, "Project not found")

@app.post("/api/projects/{project_id}/scenes")
def add_scene(project_id:str, req:SceneCreate):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    scene=req.model_dump(); scene.update({"scene_id":f"scene-{len(p.scenes)+1:03d}","status":"planned"})
    issues=validate_scene(scene,p.film_bible,p.scenes[-1] if p.scenes else None)
    scene["continuity_validation"]={"valid":not any(i.severity=="error" for i in issues),
                                    "issues":[i.__dict__ for i in issues]}
    p.scenes.append(scene); p.checkpoint={"last_valid_scene":p.scenes[-2]["scene_id"] if len(p.scenes)>1 else None}
    return save(p)

@app.post("/api/projects/{project_id}/resume")
def resume_project(project_id: str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404, "Project not found")
    return {"project_id":p.id,"resumable":True,"checkpoint":p.checkpoint,"progress":p.progress,"scenes":len(p.scenes)}
