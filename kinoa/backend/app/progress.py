from dataclasses import dataclass, field
from time import monotonic

@dataclass
class ProgressTracker:
    total:int
    started:float=field(default_factory=monotonic)
    completed:int=0
    current_scene:str|None=None
    current_progress:float=0.0
    def update(self,completed:int,current_scene:str|None=None,current_progress:float=0.0):
        self.completed=max(0,min(self.total,completed)); self.current_scene=current_scene
        self.current_progress=max(0,min(100,current_progress))
    def snapshot(self):
        elapsed=monotonic()-self.started
        overall=((self.completed+self.current_progress/100)/self.total*100) if self.total else 0
        return {"progress":round(overall,2),"completed":self.completed,"total":self.total,
                "current_scene":self.current_scene,"current_scene_progress":round(self.current_progress,2),
                "elapsed_seconds":round(elapsed,2)}
