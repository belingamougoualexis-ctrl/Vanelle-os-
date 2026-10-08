from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Hardware:
    cpu: str
    gpu: str | None
    vram_gb: float | None
    ram_gb: float | None
    disk_free_gb: float | None

@dataclass
class GenerationResult:
    scene_id: str
    output: Path
    duration_seconds: float

class VideoEngine(ABC):
    name = "abstract"

    @abstractmethod
    def capability(self, hardware: Hardware) -> tuple[bool, str]: ...

    @abstractmethod
    def generate(self, scene: dict, output_dir: Path) -> GenerationResult: ...

class Wan22Engine(VideoEngine):
    name = "wan2.2-t2v-a14b"

    def capability(self, hardware: Hardware) -> tuple[bool, str]:
        if not hardware.gpu:
            return False, "Compatible GPU not detected"
        if hardware.vram_gb is not None and hardware.vram_gb < 16:
            return False, "Insufficient VRAM for configured Wan2.2 generation"
        return True, "Hardware may support Wan2.2; model/runtime installation must be verified"

    def generate(self, scene: dict, output_dir: Path) -> GenerationResult:
        raise RuntimeError("Wan2.2 runtime is not installed in this environment; no simulated video is produced.")
