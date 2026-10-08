from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class TaskState(str,Enum):
    queued="queued"; running="running"; completed="completed"; failed="failed"; cancelled="cancelled"

@dataclass(order=True)
class GenerationTask:
    priority:int
    scene_id:str=field(compare=False)
    state:TaskState=field(default=TaskState.queued,compare=False)
    progress:float=field(default=0.0,compare=False)
    error:str|None=field(default=None,compare=False)

class Scheduler:
    def __init__(self,max_workers:int=1):
        self.max_workers=max(1,max_workers)
        self.tasks:dict[str,GenerationTask]={}
    def add(self,scene_id:str,priority:int=100)->GenerationTask:
        task=GenerationTask(priority,scene_id)
        self.tasks[scene_id]=task
        return task
    def snapshot(self)->dict[str,Any]:
        total=len(self.tasks); done=sum(t.state==TaskState.completed for t in self.tasks.values())
        running=sum(t.state==TaskState.running for t in self.tasks.values())
        progress=(sum(t.progress for t in self.tasks.values())/total) if total else 0.0
        return {"total":total,"completed":done,"running":running,"progress":round(progress,2),"max_workers":self.max_workers}
