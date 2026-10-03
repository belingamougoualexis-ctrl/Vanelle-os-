#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import torch
from PIL import Image
from torchvision import models, transforms
from torch import nn

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--checkpoint",required=True); ap.add_argument("--image",required=True)
    ap.add_argument("--top-k",type=int,default=5)
    args=ap.parse_args(); device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck=torch.load(args.checkpoint,map_location=device)
    classes=ck["classes"]; model=models.mobilenet_v3_small(weights=None)
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(classes))
    model.load_state_dict(ck["state_dict"]); model.to(device).eval()
    tf=transforms.Compose([transforms.Resize((ck["image_size"],ck["image_size"])),
                           transforms.ToTensor(),transforms.Normalize(ck["mean"],ck["std"])])
    with Image.open(args.image).convert("RGB") as im:
        x=tf(im).unsqueeze(0).to(device)
    with torch.no_grad(): probs=torch.softmax(model(x),dim=1)[0]
    vals,idx=probs.topk(min(args.top_k,len(classes)))
    preds=[{"label":classes[int(i)],"confidence":float(v)} for v,i in zip(vals,idx)]
    result={"image":str(args.image),"predicted":preds[0],"top_k":preds,"device":str(device)}
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
