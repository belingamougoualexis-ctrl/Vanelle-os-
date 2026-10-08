from fastapi import FastAPI, HTTPException
from .models import ProjectCreate, SceneCreate, FilmBibleUpdate, ScreenplaySceneCreate, SceneStatus
from .store import create, load, save
from .hardware import detect_hardware, wan22_readiness
from .continuity import validate_scene
from .orchestrator import Orchestrator
from .video_engine import get_video_engine
from .assembly import assemble_project

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
    scene["status"]=SceneStatus.planned.value
    scene["video_prompt"]=build_video_prompt(p,scene)
    p.screenplay.append(scene)
    p.checkpoint={"stage":"screenplay","last_scene_id":scene["scene_id"]}
    return save(p)

@app.get("/api/projects/{project_id}/storyboard")
def storyboard(project_id:str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    return {"project_id":p.id,"scenes":[{"scene_id":s["scene_id"],"title":s["title"],"duration_seconds":s["target_duration_seconds"],"characters":s["characters"],"location":s["location"],"status":s["status"]} for s in p.screenplay]}

@app.post("/api/projects/{project_id}/generation/plan")
def generation_plan(project_id:str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    if not p.screenplay: raise HTTPException(400,"Screenplay is empty")
    o=Orchestrator()
    validation=o.validate(p.film_bible,p.screenplay)
    if not validation["valid"]:
        raise HTTPException(409,{"message":"Continuity validation failed","issues":validation["issues"]})
    plan=o.plan(p.id,p.screenplay)
    p.generation={"state":"planned","progress":0.0,"current_scene":None,"completed":0,"total":len(plan.scene_ids),"engine":"wan2.2-t2v-a14b","error":None}
    p.checkpoint={"stage":"generation-plan","scene_ids":plan.scene_ids}
    save(p)
    return {"project_id":p.id,"plan":plan.__dict__,"validation":validation,"generation":p.generation}

@app.get("/api/projects/{project_id}/generation")
def generation_status(project_id:str):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    return p.generation

@app.post("/api/projects/{project_id}/export/assemble")
def export_assemble(project_id:str, payload:dict):
    try: p=load(project_id)
    except FileNotFoundError: raise HTTPException(404,"Project not found")
    root=payload.get("project_root")
    files=payload.get("scene_files",[])
    if not root or not files: raise HTTPException(400,"project_root and scene_files are required")
    try:
        result=assemble_project(root,files,payload.get("output","exports/final.mp4"),int(payload.get("fps",24)),int(payload.get("width",1280)),int(payload.get("height",720)))
    except (ValueError,FileNotFoundError,RuntimeError) as exc:
        raise HTTPException(422,str(exc))
    p.checkpoint={"stage":"export-assembled","output":result["output"],"qa":result["qa"]}
    save(p)
    return result

@app.get("/api/video-engine")
def video_engine():
    e=get_video_engine()
    return {"engine":e.name,"readiness":e.readiness()}

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
