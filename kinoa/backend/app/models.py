from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class SceneStatus(str, Enum):
    planned="planned"; waiting="waiting"; generation="generation"; completed="completed"; error="error"; regenerate="regenerate"

class ProjectCreate(BaseModel):
    idea: str = Field(min_length=1, max_length=10000)
    title: str | None = Field(default=None, max_length=200)
    language: str = "fr"
    genre: str = "drama"
    tone: str = "cinematic"
    duration_minutes: int = Field(default=10, ge=1, le=300)
    resolution: str = "1280x720"
    fps: int = Field(default=24, ge=1, le=120)
    visual_style: str = "cinematic realism"
    era: str = "contemporary"
    mood: str = "immersive"
    realism: float = Field(default=0.8, ge=0, le=1)
    special_instructions: str = ""

class Project(BaseModel):
    id: str
    title: str
    status: str = "draft"
    progress: float = 0
    film_bible: dict[str, Any] = Field(default_factory=dict)
    screenplay: list[dict[str, Any]] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
