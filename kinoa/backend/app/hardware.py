import os,platform,shutil

def detect_hardware():
    gpu=None; vram=None
    try:
        import torch
        if torch.cuda.is_available():
            gpu=torch.cuda.get_device_name(0)
            vram=round(torch.cuda.get_device_properties(0).total_memory/1024**3,2)
    except Exception:
        pass
    return {"cpu":platform.processor() or platform.machine(),"gpu":gpu,"vram_gb":vram,
            "ram_gb":None,"disk_free_gb":round(shutil.disk_usage("/").free/1024**3,2)}

def wan22_readiness(h):
    if not h["gpu"]: return {"ready":False,"reason":"No CUDA-compatible GPU detected"}
    if h["vram_gb"] is not None and h["vram_gb"] < 16: return {"ready":False,"reason":"Less than 16 GB VRAM detected"}
    return {"ready":True,"reason":"Hardware threshold passed; Wan2.2 runtime still requires installation and validation"}
