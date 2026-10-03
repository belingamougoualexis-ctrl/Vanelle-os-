from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser(description="Merge a real PEFT LoRA adapter into a local Transformers model")
    ap.add_argument("--model",required=True)
    ap.add_argument("--adapter",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    model_dir=Path(args.model).resolve()
    adapter_dir=Path(args.adapter).resolve()
    output_dir=Path(args.output).resolve()
    if not (adapter_dir / "adapter_config.json").is_file():
        raise RuntimeError("Adaptateur PEFT invalide: adapter_config.json introuvable.")
    output_dir.mkdir(parents=True,exist_ok=True)

    dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    base=AutoModelForCausalLM.from_pretrained(
        model_dir, local_files_only=True, torch_dtype=dtype, low_cpu_mem_usage=True
    )
    model=PeftModel.from_pretrained(base,adapter_dir,local_files_only=True)
    merged=model.merge_and_unload()
    merged.save_pretrained(output_dir,safe_serialization=True)
    tokenizer=AutoTokenizer.from_pretrained(model_dir,local_files_only=True)
    tokenizer.save_pretrained(output_dir)
    manifest={
        "format":"transformers",
        "merged_from":str(model_dir),
        "adapter":str(adapter_dir),
        "device":"cuda" if torch.cuda.is_available() else "cpu",
        "files":len([p for p in output_dir.rglob('*') if p.is_file()]),
    }
    (output_dir/"vanelle_merge_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("REAL_MODEL_MERGE_OK",flush=True)
    print(json.dumps(manifest,ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REAL_MODEL_MERGE_ERROR: {exc}",file=sys.stderr,flush=True)
        raise