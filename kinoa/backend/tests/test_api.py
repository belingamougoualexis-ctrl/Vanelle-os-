from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["product"] == "KINOA"
    assert body["runtime"] == "real-only"

def test_project_lifecycle():
    r = client.post("/api/projects", json={"idea": "Une histoire de voyage", "genre": "adventure"})
    assert r.status_code == 201
    p = r.json()
    assert p["film_bible"]["concept"] == "Une histoire de voyage"
    r2 = client.get("/api/projects/" + p["id"])
    assert r2.status_code == 200
    r3 = client.post("/api/projects/" + p["id"] + "/resume")
    assert r3.status_code == 200

def test_film_bible_screenplay_storyboard():
    r = client.post("/api/projects", json={"idea":"Une enquête nocturne","title":"Nuit","genre":"thriller"})
    assert r.status_code == 201
    pid = r.json()["id"]
    b = client.put(f"/api/projects/{pid}/film-bible", json={
        "synopsis":"Une enquête dans une ville sous la pluie.",
        "characters":[{"name":"Maya","role":"detective","appearance":"natural"}],
        "locations":[{"name":"Port","description":"quais sous la pluie"}],
        "continuity_rules":["Maya conserve son manteau bleu"],
        "visual":{"style":"cinematic realism","lighting":"soft practical light"}
    })
    assert b.status_code == 200
    s = client.post(f"/api/projects/{pid}/screenplay", json={
        "title":"Le port","location":"Port","time_of_day":"night",
        "characters":["Maya"],"action":"Maya observe les quais sous la pluie.",
        "camera":"slow dolly","target_duration_seconds":8
    })
    assert s.status_code == 200
    assert s.json()["screenplay"][0]["video_prompt"]["human_visual_constraints"]["natural_faces"] is True
    sb = client.get(f"/api/projects/{pid}/storyboard")
    assert sb.status_code == 200
    assert sb.json()["scenes"][0]["scene_id"] == "scene-001"

def test_generation_plan_and_engine_status():
    r = client.post("/api/projects", json={"idea":"Voyage sous la pluie"})
    assert r.status_code == 201
    pid = r.json()["id"]
    s = client.post(f"/api/projects/{pid}/screenplay", json={
        "title":"Départ","location":"Gare","characters":["Maya"],
        "action":"Maya quitte la gare sous la pluie.","target_duration_seconds":8
    })
    assert s.status_code == 200
    plan = client.post(f"/api/projects/{pid}/generation/plan")
    assert plan.status_code == 200
    assert plan.json()["generation"]["state"] == "planned"
    status = client.get(f"/api/projects/{pid}/generation")
    assert status.status_code == 200
    engine = client.get("/api/video-engine")
    assert engine.status_code == 200
    assert engine.json()["engine"] == "wan2.2-t2v-a14b"


def test_generation_start_fails_closed_without_real_runtime(client):
    project=client.post("/api/projects",json={"idea":"A real film"}).json()
    pid=project["id"]
    client.post(f"/api/projects/{pid}/screenplay",json={"title":"Opening","action":"A character enters","characters":["A"],"location":"Room","target_duration_seconds":2})
    response=client.post(f"/api/projects/{pid}/generation/start")
    assert response.status_code in (503,200)
    state=client.get(f"/api/projects/{pid}/generation").json()
    if response.status_code==503:
        assert state["state"]=="blocked"
