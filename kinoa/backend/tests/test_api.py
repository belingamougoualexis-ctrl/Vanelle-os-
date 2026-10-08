from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app

client=TestClient(app)

def test_health():
    r=client.get("/health"); assert r.status_code==200; assert r.json()["simulation"] is False

def test_project_lifecycle():
    r=client.post("/api/projects",json={"idea":"Une histoire de voyage","genre":"adventure"})
    assert r.status_code==201
    p=r.json(); assert p["film_bible"]["concept"]=="Une histoire de voyage"
    r2=client.get("/api/projects/"+p["id"]); assert r2.status_code==200
    r3=client.post("/api/projects/"+p["id"]+"/resume"); assert r3.status_code==200
