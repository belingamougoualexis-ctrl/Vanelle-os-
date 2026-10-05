from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

def render_prompt(tokenizer, test: dict[str, Any]) -> str:
    messages = test.get("messages")
    if isinstance(messages, list) and messages:
        clean = [{"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
                 for m in messages if isinstance(m, dict)]
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                return tokenizer.apply_chat_template(clean, tokenize=False, add_generation_prompt=True)
            except Exception:
                pass
        return "\n".join(f"{m['role']}: {m['content']}" for m in clean)
    return str(test.get("prompt", "")).strip()

def score(answer: str, test: dict[str, Any]) -> tuple[bool, int, list[str]]:
    reasons = []
    total = 0
    points = 0
    lower = answer.lower()
    min_chars = int(test.get("min_chars", 0))
    max_chars = int(test.get("max_chars", 0))
    if min_chars:
        total += 1
        if len(answer) >= min_chars: points += 1
        else: reasons.append(f"Réponse trop courte: {len(answer)} caractères.")
    if max_chars:
        total += 1
        if len(answer) <= max_chars: points += 1
        else: reasons.append(f"Réponse trop longue: {len(answer)} caractères.")
    for token in test.get("must_contain", []) or []:
        total += 1
        if str(token).lower() in lower: points += 1
        else: reasons.append(f"Élément attendu absent: {token}")
    for token in test.get("must_not_contain", []) or []:
        total += 1
        if str(token).lower() not in lower: points += 1
        else: reasons.append(f"Élément interdit détecté: {token}")
    if total == 0:
        total = 1
        points = 1 if answer.strip() else 0
    value = int(points * 100 / total)
    return value >= 80, value, reasons

def main() -> int:
    ap = argparse.ArgumentParser(description="Real generation-based evaluation for a trained model")
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default="")
    ap.add_argument("--tests", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=128)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    model_dir = Path(args.model).resolve()
    adapter_dir = Path(args.adapter).resolve() if args.adapter else None
    tests = json.loads(Path(args.tests).read_text(encoding="utf-8"))
    if not isinstance(tests, list) or not tests:
        raise RuntimeError("Aucun scénario d'évaluation.")

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        low_cpu_mem_usage=True,
    )
    if adapter_dir:
        model = PeftModel.from_pretrained(model, adapter_dir, local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    results=[]
    for test in tests:
        prompt = render_prompt(tokenizer, test)
        if not prompt:
            results.append({"name": test.get("name","Unnamed"), "response":"", "passed":False,
                            "score":0, "reasons":["Scénario sans prompt."]})
            continue
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        generated = output[0][inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
        passed, value, reasons = score(answer, test)
        results.append({
            "name": test.get("name","Unnamed"),
            "response": answer,
            "passed": passed,
            "score": value,
            "reasons": reasons,
        })

    passed = sum(1 for x in results if x["passed"])
    failed = len(results) - passed
    report = {
        "passed": passed,
        "failed": failed,
        "average_score": int(sum(x["score"] for x in results) / len(results)),
        "results": results,
        "device": str(device),
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REAL_HF_EVALUATION_OK", flush=True)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REAL_HF_EVALUATION_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
