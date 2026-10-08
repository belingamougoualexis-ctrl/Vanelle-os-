from app.continuity import validate_scene
from app.scheduler import Scheduler
from app.progress import ProgressTracker
from app.hardware import wan22_readiness

def test_continuity_catches_unexpected_change():
    issues=validate_scene({"scene_id":"2","characters":[],"location":"B","visual_style":"A","duration_seconds":5},{"continuity_rules":[]},{"location":"A","visual_style":"A"})
    assert any(i.field=="location" for i in issues)

def test_scheduler_progress():
    s=Scheduler(2); s.add("1"); s.add("2",10); s.tasks["1"].progress=50
    assert s.snapshot()["total"]==2 and s.snapshot()["progress"]==25

def test_progress():
    p=ProgressTracker(2); p.update(1,"2",50)
    assert p.snapshot()["progress"]==75

def test_wan_readiness_requires_gpu():
    r=wan22_readiness({"gpu":None,"vram_gb":None})
    assert r["ready"] is False
