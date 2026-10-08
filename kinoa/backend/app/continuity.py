from dataclasses import dataclass
from typing import Any

@dataclass
class ContinuityIssue:
    field: str
    message: str
    severity: str = "error"

def validate_scene(scene: dict[str, Any], bible: dict[str, Any], previous: dict[str, Any] | None = None) -> list[ContinuityIssue]:
    issues=[]
    required=("scene_id","characters","location","visual_style","duration_seconds")
    for key in required:
        if key not in scene:
            issues.append(ContinuityIssue(key,f"Missing continuity field: {key}"))
    if previous:
        for key in ("visual_style","location"):
            if previous.get(key) and scene.get(key) and scene[key] != previous[key] and not scene.get("transition"):
                issues.append(ContinuityIssue(key,f"Unexpected change from previous scene: {key}"))
    rules=bible.get("continuity_rules",[])
    for rule in rules:
        if isinstance(rule,str) and rule and rule.lower() not in str(scene).lower():
            issues.append(ContinuityIssue("rule",f"Continuity rule not evidenced: {rule}","warning"))
    return issues

def build_scene_context(bible: dict[str,Any], previous: dict[str,Any] | None, scene: dict[str,Any]) -> dict[str,Any]:
    return {"film_bible":bible,"previous_scene":previous or {},"current_scene":scene,"human_visual_constraints":{
        "natural_faces":True,"credible_expressions":True,"realistic_motion":True,
        "stable_identity":True,"stable_clothing":True,"stable_objects":True,
        "plausible_physics":True,"cinematic_lighting":True}}

# Empty optional scene fields inherit context rather than creating a false continuity break.
