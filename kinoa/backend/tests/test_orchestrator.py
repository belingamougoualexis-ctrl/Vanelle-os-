from app.orchestrator import Orchestrator
from app.video_engine import Wan22Engine

def test_orchestrator_plan_and_continuity():
    scenes = [
        {"scene_id":"scene-001","characters":["Maya"],"location":"Port","visual_style":"cinematic","duration_seconds":8},
        {"scene_id":"scene-002","characters":["Maya"],"location":"Port","visual_style":"cinematic","duration_seconds":8},
    ]
    o = Orchestrator(2)
    plan = o.plan("p1", scenes)
    assert plan.scene_ids == ["scene-001","scene-002"]
    assert o.validate({"continuity_rules":[]}, scenes)["valid"] is True
    assert len(o.contexts({"continuity_rules":[]}, scenes)) == 2

def test_wan_engine_never_claims_generation_without_runtime():
    e = Wan22Engine()
    result = e.readiness()
    assert result["ready"] is False
    assert result["engine"] == "wan2.2-t2v-a14b"
