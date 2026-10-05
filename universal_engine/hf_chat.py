from __future__ import annotations

import argparse
import json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",required=True)
    ap.add_argument("--adapter",default="")
    ap.add_argument("--messages",required=True)
    ap.add_argument("--max-new-tokens",type=int,default=256)
    args=ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    model_dir=Path(args.model).resolve()
    tokenizer=AutoTokenizer.from_pretrained(model_dir,local_files_only=True)
    if tokenizer.pad_token is None: tokenizer.pad_token=tokenizer.eos_token
    model=AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        low_cpu_mem_usage=True,
    )
    if args.adapter:
        model=PeftModel.from_pretrained(model,Path(args.adapter).resolve(),local_files_only=True)
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device); model.eval()
    messages=json.loads(Path(args.messages).read_text(encoding="utf-8"))
    if hasattr(tokenizer,"apply_chat_template"):
        try:
            prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        except Exception:
            prompt="\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in messages)
    else:
        prompt="\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in messages)
    inputs=tokenizer(prompt,return_tensors="pt").to(device)
    with torch.no_grad():
        out=model.generate(**inputs,max_new_tokens=args.max_new_tokens,do_sample=False,pad_token_id=tokenizer.pad_token_id)
    text=tokenizer.decode(out[0][inputs["input_ids"].shape[1]:],skip_special_tokens=True).strip()
    if not text: raise RuntimeError("Le modèle n'a produit aucune réponse.")
    print(text,flush=True)

if __name__=="__main__":
    main()
