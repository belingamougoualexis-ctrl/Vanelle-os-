from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class GenerationRequest:
    scene_id: str
    prompt: dict[str, Any]
    output_path: Path
    duration_seconds: float
    width: int
    height: int
    fps: int

class VideoEngine(ABC):
    name = "abstract"
    @abstractmethod
    def readiness(self) -> dict[str, Any]: ...
    @abstractmethod
    def generate(self, request: GenerationRequest, progress_callback=None) -> Path: ...

class Wan22Engine(VideoEngine):
    name = "wan2.2-t2v-a14b"
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
    def readiness(self):
        try:
            import torch
        except ImportError:
            return {"ready": False, "reason": "PyTorch is not installed", "engine": self.name}
        if not torch.cuda.is_available():
            return {"ready": False, "reason": "CUDA GPU is unavailable", "engine": self.name}
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        if vram < 16:
            return {"ready": False, "reason": "Less than 16 GB VRAM", "engine": self.name, "vram_gb": round(vram, 2)}
        if not self.model_path:
            return {"ready": False, "reason": "Wan2.2 model path is not configured", "engine": self.name}
        if not Path(self.model_path).exists():
            return {"ready": False, "reason": "Configured Wan2.2 model path does not exist", "engine": self.name}
        return {"ready": True, "reason": "Hardware and model path checks passed; runtime generation still requires model compatibility validation", "engine": self.name}
    def generate(self, request, progress_callback=None):
        status = self.readiness()
        if not status["ready"]:
            raise RuntimeError(f'Wan2.2 unavailable: {status["reason"]}')
        raise NotImplementedError("Wan2.2 runtime adapter is not executed until its exact installed model/runtime is validated.")

def get_video_engine(name: str = "wan2.2-t2v-a14b", model_path: str | None = None) -> VideoEngine:
    if name == "wan2.2-t2v-a14b":
        return Wan22Engine(model_path)
    raise ValueError(f"Unsupported video engine: {name}")
