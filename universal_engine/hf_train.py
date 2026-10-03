from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

def log(msg: str) -> None:
    print(msg, flush=True)

def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Dataset JSONL invalide ligne {line_no}: {exc}") from exc
        records.append(value)
    if not records:
        raise RuntimeError("Le dataset ne contient aucun exemple.")
    return records

def render_example(tokenizer, record: dict[str, Any]) -> str:
    messages = record.get("messages")
    if isinstance(messages, list) and messages:
        clean = [
            {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
            for m in messages if isinstance(m, dict) and str(m.get("content", "")).strip()
        ]
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                return tokenizer.apply_chat_template(
                    clean, tokenize=False, add_generation_prompt=False
                )
            except Exception:
                pass
        return "\n".join(f"{m['role']}: {m['content']}" for m in clean)

    text = str(record.get("text", "")).strip()
    if not text:
        raise RuntimeError("Exemple sans 'messages' ni 'text'.")
    return text

def make_dataset(tokenizer, records, max_length: int):
    from datasets import Dataset

    texts = [render_example(tokenizer, r) for r in records]
    ds = Dataset.from_dict({"text": texts})

    def tokenize(batch):
        out = tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        out["labels"] = [ids[:] for ids in out["input_ids"]]
        return out

    return ds.map(tokenize, batched=True, remove_columns=["text"])

def main() -> int:
    ap = argparse.ArgumentParser(description="Real local Transformers + PEFT LoRA trainer")
    ap.add_argument("--model", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--objective", default="")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--learning-rate", type=float, default=2e-5)
    ap.add_argument("--max-length", type=int, default=1024)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--alpha", type=int, default=16)
    args = ap.parse_args()

    model_dir = Path(args.model).resolve()
    dataset_path = Path(args.dataset).resolve()
    output_dir = Path(args.output).resolve()
    if not (model_dir / "config.json").is_file():
        raise RuntimeError("Modèle Transformers invalide : config.json introuvable.")
    output_dir.mkdir(parents=True, exist_ok=True)

    log("VANELLE UNIVERSAL TRAINING / Transformers + PEFT")
    log(f"MODEL={model_dir}")
    log(f"DATASET={dataset_path}")
    log(f"OUTPUT={output_dir}")
    log(f"OBJECTIVE={args.objective}")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training

    records = load_records(dataset_path)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.float32
    if torch.cuda.is_available():
        if torch.cuda.is_bf16_supported():
            dtype = torch.bfloat16
        else:
            dtype = torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        torch_dtype=dtype if torch.cuda.is_available() else torch.float32,
        low_cpu_mem_usage=True,
    )
    if getattr(model.config, "use_cache", None) is not None:
        model.config.use_cache = False

    try:
        model = prepare_model_for_kbit_training(model)
    except Exception:
        pass

    def target_modules_for_model() -> str | list[str]:
        model_type = str(getattr(model.config, "model_type", "")).lower()
        if model_type in {"gpt2", "gpt_bigcode"}:
            return ["c_attn", "c_proj", "c_fc"]
        if model_type in {"llama", "mistral", "qwen2", "qwen3", "gemma", "gemma2", "gemma3",
                          "phi3", "phi4", "qwen2_moe", "mixtral"}:
            return ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        return "all-linear"

    target_modules = target_modules_for_model()
    lora = LoraConfig(
        r=args.rank,
        lora_alpha=args.alpha,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=target_modules,
    )
    try:
        model = get_peft_model(model, lora)
    except ValueError as exc:
        if target_modules != "all-linear":
            raise
        linear_names = {
            name.split(".")[-1]
            for name, module in model.named_modules()
            if module.__class__.__name__ == "Linear" and not name.endswith("lm_head")
        }
        if not linear_names:
            raise RuntimeError(f"Impossible de déterminer les modules LoRA pour {model.config.model_type}: {exc}") from exc
        fallback = sorted(linear_names)
        log(f"LoRA fallback modules: {fallback}")
        lora = LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=fallback,
        )
        model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = make_dataset(tokenizer, records, args.max_length)
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    from transformers import Trainer, TrainingArguments
    training_kwargs = dict(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=max(1, args.batch_size),
        gradient_accumulation_steps=1,
        learning_rate=args.learning_rate,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],
        remove_unused_columns=False,
    )
    if torch.cuda.is_available():
        training_kwargs["fp16"] = not torch.cuda.is_bf16_supported()
        training_kwargs["bf16"] = torch.cuda.is_bf16_supported()
    import inspect
    supported = set(inspect.signature(TrainingArguments.__init__).parameters)
    training_kwargs = {k:v for k,v in training_kwargs.items() if k in supported}
    train_args = TrainingArguments(**training_kwargs)

    trainer_kwargs = dict(
        model=model,
        args=train_args,
        train_dataset=ds,
        data_collator=collator,
    )
    try:
        trainer = Trainer(processing_class=tokenizer, **trainer_kwargs)
    except TypeError:
        trainer = Trainer(tokenizer=tokenizer, **trainer_kwargs)

    result = trainer.train()
    model.save_pretrained(output_dir / "adapter")
    tokenizer.save_pretrained(output_dir / "adapter")

    summary = {
        "format": "transformers-peft-lora",
        "model": str(model_dir),
        "dataset": str(dataset_path),
        "objective": args.objective,
        "examples": len(records),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "training_loss": float(result.training_loss) if result.training_loss is not None else None,
    }
    (output_dir / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("REAL_TRAINING_OK")
    log(json.dumps(summary, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REAL_TRAINING_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
