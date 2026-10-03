# /// script
# dependencies = ["torch", "transformers", "datasets", "peft", "accelerate"]
# ///
import json, os, time
from datasets import load_dataset, Dataset
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer, DataCollatorForLanguageModeling, set_seed
from peft import LoraConfig, get_peft_model

set_seed(42)
if not torch.cuda.is_available(): raise SystemExit("REAL_GPU_TRAINING_REQUIRED: CUDA unavailable")
print("ALPHAPRIME_REAL_FINETUNE=1")
print("GPU=", torch.cuda.get_device_name(0))
print("VRAM_GB=", round(torch.cuda.get_device_properties(0).total_memory/1024**3,2))

base="HuggingFaceTB/SmolLM2-360M-Instruct"
raw=load_dataset("OpenAssistant/oasst1", split="train")
by_id={r["message_id"]:r for r in raw}
examples=[]
for r in raw:
    if len(examples)>=64: break
    if r.get("role")!="assistant" or r.get("lang")!="en" or r.get("deleted") or r.get("synthetic"): continue
    parent=by_id.get(r.get("parent_id"))
    if not parent or parent.get("role")!="prompter" or parent.get("lang")!="en" or parent.get("deleted") or parent.get("synthetic"): continue
    q=str(parent.get("text","")).strip(); a=str(r.get("text","")).strip()
    if not q or not a: continue
    examples.append({"text":f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n{a}<|im_end|>"})
if len(examples)<32: raise SystemExit(f"Not enough non-synthetic real pairs: {len(examples)}")
dataset=Dataset.from_list(examples)
print("TRAINING_EXAMPLES=",len(dataset))

tokenizer=AutoTokenizer.from_pretrained(base)
if tokenizer.pad_token is None: tokenizer.pad_token=tokenizer.eos_token
def tok(batch): return tokenizer(batch["text"],truncation=True,max_length=256)
tokenized=dataset.map(tok,batched=True,remove_columns=["text"])
model=AutoModelForCausalLM.from_pretrained(base,torch_dtype=torch.float16)
cfg=LoraConfig(r=8,lora_alpha=16,lora_dropout=0.05,target_modules=["q_proj","v_proj"],task_type="CAUSAL_LM")
model=get_peft_model(model,cfg)
model.print_trainable_parameters()

args=TrainingArguments(output_dir="/data/alphaprime_adapter",num_train_epochs=1,per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=2e-4,logging_steps=1,save_strategy="no",report_to=[],fp16=True,remove_unused_columns=False)
trainer=Trainer(model=model,args=args,train_dataset=tokenized,data_collator=DataCollatorForLanguageModeling(tokenizer,mlm=False))
t0=time.perf_counter()
result=trainer.train()
elapsed=time.perf_counter()-t0
model.save_pretrained("/data/alphaprime_adapter")
tokenizer.save_pretrained("/data/alphaprime_adapter")

prompt="<|im_start|>user\nExplain in one sentence what a local AI system means.\n<|im_end|>\n<|im_start|>assistant\n"
inputs=tokenizer(prompt,return_tensors="pt").to(model.device)
with torch.no_grad(): out=model.generate(**inputs,max_new_tokens=32,do_sample=False)
decoded=tokenizer.decode(out[0],skip_special_tokens=False)
train_loss=float(result.training_loss) if getattr(result,"training_loss",None) is not None else None
report={"truth_status":"REAL","base_model":base,"dataset":"OpenAssistant/oasst1","synthetic_filtered":True,"examples":len(dataset),"train_loss":train_loss,"seconds":round(elapsed,2),"gpu":torch.cuda.get_device_name(0),"output":decoded[-1200:]}
print(json.dumps(report,ensure_ascii=False))
if not decoded.strip(): raise SystemExit("Post-training generation empty")
print("ALPHAPRIME_REAL_FINETUNE_PASS=1")