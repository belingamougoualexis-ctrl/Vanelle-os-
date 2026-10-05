import argparse,json,os,re,torch
from peft import PeftModel
from transformers import AutoModelForCausalLM,AutoTokenizer

def rows(path):
    with open(path,encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]

def gen(model,tok,msgs):
    prompt=tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True)
    x=tok(prompt,return_tensors="pt").to(model.device)
    with torch.no_grad(): y=model.generate(**x,max_new_tokens=96,do_sample=False,pad_token_id=tok.pad_token_id,eos_token_id=tok.eos_token_id)
    return tok.decode(y[0][x["input_ids"].shape[-1]:],skip_special_tokens=True).strip()

def score(text,need):
    t=re.sub(r"\s+"," ",text.lower())
    return sum(1 for s in need if s.lower() in t)/max(1,len(need))

def run(model,tok,data):
    out=[]
    for r in data:
        ans=gen(model,tok,r["messages"]); out.append({"id":r["id"],"score":score(ans,r["must_include"]),"answer":ans})
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument("--base-model",required=True); p.add_argument("--adapter",required=True); p.add_argument("--test",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    data=rows(a.test); tok=AutoTokenizer.from_pretrained(a.base_model,use_fast=True)
    if tok.pad_token is None: tok.pad_token=tok.eos_token
    base=AutoModelForCausalLM.from_pretrained(a.base_model,torch_dtype=torch.float32,low_cpu_mem_usage=True)
    before=run(base,tok,data); del base
    adapted_base=AutoModelForCausalLM.from_pretrained(a.base_model,torch_dtype=torch.float32,low_cpu_mem_usage=True)
    adapted=PeftModel.from_pretrained(adapted_base,a.adapter); adapted.eval(); after=run(adapted,tok,data)
    b=sum(x["score"] for x in before)/len(before); c=sum(x["score"] for x in after)/len(after)
    report={"base_model":a.base_model,"test_examples":len(data),"before_average":b,"after_average":c,"delta":c-b,"improvement_verified":c>b,"baseline":before,"nexa":after}
    os.makedirs(os.path.dirname(a.output),exist_ok=True)
    with open(a.output,"w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:report[k] for k in ["before_average","after_average","delta","improvement_verified"]},ensure_ascii=False))

if __name__=="__main__": main()
