from __future__ import annotations

import argparse
import json
from pathlib import Path

WEIGHT_SUFFIXES={".safetensors",".bin",".pt",".pth",".ckpt"}

def inspect(path: str) -> dict:
    p=Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(path)
    if p.is_file():
        if p.suffix.lower()==".gguf":
            with p.open("rb") as f:
                if f.read(4)!=b"GGUF": raise RuntimeError("Signature GGUF invalide.")
            return {"format":"gguf","id":p.stem,"path":str(p)}
        raise RuntimeError("Format fichier non pris en charge.")
    cfg=p/"config.json"
    weights=[x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in WEIGHT_SUFFIXES]
    if not cfg.is_file() or not weights:
        raise RuntimeError("Dossier modèle invalide: config.json et poids attendus.")
    data=json.loads(cfg.read_text(encoding="utf-8"))
    arch=(data.get("architectures") or [None])[0]
    model_type=data.get("model_type")
    size=sum(x.stat().st_size for x in p.rglob("*") if x.is_file())
    return {
        "format":"transformers",
        "id":p.name,
        "path":str(p),
        "family":model_type or "unknown",
        "architecture":arch or "unknown",
        "weight_files":len(weights),
        "size_bytes":size,
        "torch_dtype":data.get("torch_dtype"),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path")
    print(json.dumps(inspect(ap.parse_args().path),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
