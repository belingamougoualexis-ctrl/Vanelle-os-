import argparse, json, os, random
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling, Trainer, TrainingArguments

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base-model",default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--train",required=True); p.add_argument("--output",required=True)
    p.add_argument("--epochs",type=float,default=1.0); p.add_argument("--max-length",type=int,default=384)
    a=p.parse_args()
    os.makedirs(a.output,exist_ok=True); random.seed(42); torch.manual_seed(42)
    tok=AutoTokenizer.from_pretrained(a.base_model,use_fast=True)
    if tok.pad_token is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(a.base_model,torch_dtype=torch.float32,low_cpu_mem_usage=True)
    model.config.use_cache=False
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,bias="none",task_type="CAUSAL_LM",target_modules=["q_proj","v_proj"]))
    rows=load_jsonl(a.train); ds=Dataset.from_list(rows)
    def enc(row):
        text=tok.apply_chat_template(row["messages"],tokenize=False,add_generation_prompt=False)
        x=tok(text,truncation=True,max_length=a.max_length,padding="max_length")
        x["labels"]=list(x["input_ids"]); return x
    ds=ds.map(enc,remove_columns=ds.column_names)
    args=TrainingArguments(output_dir=a.output,num_train_epochs=a.epochs,per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=2e-4,weight_decay=.01,logging_steps=1,save_strategy="no",report_to="none",fp16=False,bf16=False,dataloader_num_workers=0)
    trainer=Trainer(model=model,args=args,train_dataset=ds,data_collator=DataCollatorForLanguageModeling(tokenizer=tok,mlm=False))
    result=trainer.train(); trainer.save_model(a.output); tok.save_pretrained(a.output)
    with open(os.path.join(a.output,"nexa_training.json"),"w",encoding="utf-8") as f:
        json.dump({"base_model":a.base_model,"examples":len(rows),"epochs":a.epochs,"device":"cuda" if torch.cuda.is_available() else "cpu","train_loss":float(result.training_loss)},f,ensure_ascii=False,indent=2)

if __name__=="__main__": main()
