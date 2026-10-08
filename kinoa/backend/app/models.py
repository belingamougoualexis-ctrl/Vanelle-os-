from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class SceneStatus(str, Enum):
    planned="planned"; waiting="waiting"; generation="generation"; completed="completed"; error="error"; regenerate="regenerate"

class SceneCreate(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    location:str=""
    time_of_day:str="day"
    characters:list[str]=Field(default_factory=list)
    action:str=""
    dialogue:str=""
    atmosphere:str=""
    camera:str=""
    visual_style:str=""
    target_duration_seconds:float=Field(default=8,gt=0,le=600)
    dependencies:list[str]=Field(default_factory=list)

class FilmBibleUpdate(BaseModel):
    concept:str|None=None
    synopsis:str|None=None
    themes:list[str]|None=None
    world:dict[str,Any]|None=None
    characters:list[dict[str,Any]]|None=None
    locations:list[dict[str,Any]]|None=None
    visual:dict[str,Any]|None=None
    continuity_rules:list[str]|None=None

class ScreenplaySceneCreate(BaseModel):
    scene_id:str|None=None
    title:str=Field(min_length=1,max_length=200)
    location:str=""
    time_of_day:str="day"
    characters:list[str]=Field(default_factory=list)
    action:str=""
    dialogue:str=""
    atmosphere:str=""
    camera:str=""
    visual_style:str=""
    target_duration_seconds:float=Field(default=8,gt=0,le=600)
    dependencies:list[str]=Field(default_factory=list)

class ProjectCreate(BaseModel):
    idea: str = Field(min_length=1, max_length=10000)
    title: str | None = Field(default=None, max_length=200)
    language: str = "fr"; genre: str = "drama"; tone: str = "cinematic"
    duration_minutes: int = Field(default=10, ge=1, le=300)
    resolution: str = "1280x720"; fps: int = Field(default=24, ge=1, le=120)
    visual_style: str = "cinematic realism"; era: str = "contemporary"; mood: str = "immersive"
    realism: float = Field(default=0.8, ge=0, le=1); special_instructions: str = ""

class Project(BaseModel):
    id: str; title: str; status: str = "draft"; progress: float = 0
    film_bible: dict[str, Any] = Field(default_factory=dict)
    screenplay: list[dict[str, Any]] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
