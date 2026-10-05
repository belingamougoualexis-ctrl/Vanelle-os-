# NEXA — General AI foundation

NEXA is the first custom AI project created with Vanelle.

## Goal
Build a general-purpose French-first assistant that can progressively improve at instruction following, reasoning, mathematics, coding, writing, document understanding, multilingual assistance and tool-oriented workflows.

## Honest scope of v0.1
v0.1 is a real LoRA adaptation of Qwen2.5-0.5B-Instruct. It is a foundation experiment, not a claim of frontier-level performance. The benchmark is held out from training and is used to decide whether the adapted model actually improves.

## Reproducibility
- Base model: Qwen/Qwen2.5-0.5B-Instruct
- Training: Transformers + PEFT LoRA
- Evaluation: independent held-out prompts
- Artifact: LoRA adapter + metrics + generations

The base model remains hosted by its original provider; this repository contains NEXA's training data, code, and produced adapter artifacts.
