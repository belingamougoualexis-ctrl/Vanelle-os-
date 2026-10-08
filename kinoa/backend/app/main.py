from fastapi import FastAPI, HTTPException
from .models import ProjectCreate, SceneCreate, FilmBibleUpdate, ScreenplaySceneCreate
from .store import create, load, save
from .hardware import detect_hardware, wan22_readiness
from .continuity import validate_scene

app = FastAPI(title="KINOA API", version="0.3.0")

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

@app.put("/api/projects/{project_id}/film-bible")
def update_film_bible(project_id:str, req:FilmBibleUpdate):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    data=req.model_dump(exclude_none=True)
    p.film_bible.update(data)
    p.checkpoint={"stage":"film-bible","saved":True}
    return save(p)

@app.get("/api/projects/{project_id}/film-bible")
def get_film_bible(project_id:str):
    try: return load(project_id).film_bible
    except FileNotFoundError: raise HTTPException(404,"Project not found")

@app.post("/api/projects/{project_id}/screenplay")
def add_screenplay_scene(project_id:str, req:ScreenplaySceneCreate):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    scene=req.model_dump()
    scene["scene_id"]=scene["scene_id"] or f"scene-{len(p.screenplay)+1:03d}"
    scene["status"]=SceneStatus.planned.value if hasattr(SceneStatus,"planned") else "planned"
    scene["video_prompt"]=build_video_prompt(p,scene)
    p.screenplay.append(scene)
    p.checkpoint={"stage":"screenplay","last_scene_id":scene["scene_id"]}
    return save(p)

@app.get("/api/projects/{project_id}/storyboard")
def storyboard(project_id:str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    return {"project_id":p.id,"scenes":[{"scene_id":s["scene_id"],"title":s["title"],"duration_seconds":s["target_duration_seconds"],"characters":s["characters"],"location":s["location"],"status":s["status"]} for s in p.screenplay]}

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

def build_video_prompt(project, scene):
    bible=project.film_bible
    visual=bible.get("visual",{})
    continuity=bible.get("continuity_rules",[])
    return {
        "scene":scene["action"],"characters":scene["characters"],"location":scene["location"],
        "time_of_day":scene["time_of_day"],"camera":scene["camera"],
        "visual_style":scene["visual_style"] or visual.get("style","cinematic realism"),
        "film_bible":bible,"continuity_rules":continuity,
        "human_visual_constraints":{"natural_faces":True,"credible_expressions":True,"realistic_motion":True,
        "stable_identity":True,"stable_clothing":True,"stable_objects":True,"plausible_physics":True}
    }
