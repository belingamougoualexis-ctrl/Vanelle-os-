from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .continuity import validate_scene, build_scene_context
from .scheduler import Scheduler
from .progress import ProgressTracker

@dataclass
class OrchestrationPlan:
    project_id: str
    scene_ids: list[str]
    max_workers: int

class Orchestrator:
    def __init__(self, max_workers: int = 1):
        self.scheduler = Scheduler(max_workers=max_workers)
    def plan(self, project_id: str, scenes: list[dict[str, Any]]) -> OrchestrationPlan:
        for scene in scenes:
            self.scheduler.add(scene["scene_id"], priority=100)
        return OrchestrationPlan(project_id, [s["scene_id"] for s in scenes], self.scheduler.max_workers)
    def validate(self, bible: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
        issues = {}
        previous = None
        for scene in scenes:
            found = validate_scene(scene, bible, previous)
            issues[scene["scene_id"]] = [i.__dict__ for i in found]
            previous = scene
        return {"valid": not any(x for x in issues.values() if any(i["severity"] == "error" for i in x)), "issues": issues}
    def contexts(self, bible: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        previous = None
        result = []
        for scene in scenes:
            result.append(build_scene_context(bible, previous, scene))
            previous = scene
        return result
    def progress(self, scenes: list[dict[str, Any]]) -> dict[str, Any]:
        tracker = ProgressTracker(len(scenes))
        for index, scene in enumerate(scenes):
            tracker.update(index, scene["scene_id"], 0)
        return tracker.snapshot()
