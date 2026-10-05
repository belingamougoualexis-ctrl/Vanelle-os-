#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torchvision.models import MobileNet_V3_Small_Weights
from torch import nn

def load_model(checkpoint:Path, device):
    ck=torch.load(checkpoint,map_location=device)
    classes=ck["classes"]; model=models.mobilenet_v3_small(weights=None)
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(classes))
    model.load_state_dict(ck["state_dict"]); model.to(device).eval()
    return model,classes,ck

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",required=True); ap.add_argument("--checkpoint",required=True)
    ap.add_argument("--output",required=True); ap.add_argument("--batch-size",type=int,default=16)
    args=ap.parse_args(); device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck=torch.load(args.checkpoint,map_location=device)
    tf=transforms.Compose([transforms.Resize((ck["image_size"],ck["image_size"])),
                           transforms.ToTensor(),transforms.Normalize(ck["mean"],ck["std"])])
    full=datasets.ImageFolder(args.dataset,transform=tf)
    indices=ck.get("val_indices")
    if not indices: raise SystemExit("Le checkpoint ne contient pas de validation holdout.")
    ds=torch.utils.data.Subset(full,indices)
    model,classes,_=load_model(Path(args.checkpoint),device)
    correct=0; total=0; per={c:{"correct":0,"total":0} for c in classes}
    with torch.no_grad():
        for x,y in DataLoader(ds,batch_size=args.batch_size,shuffle=False,num_workers=0):
            pred=model(x.to(device)).argmax(1).cpu()
            for yi,pi in zip(y.tolist(),pred.tolist()):
                total+=1; c=classes[yi]; per[c]["total"]+=1
                if yi==pi: correct+=1; per[c]["correct"]+=1
    acc=correct/max(1,total)
    report={"format":"vision-evaluation","images":total,"accuracy":acc,
            "device":str(device),"classes":classes,
            "per_class":{c:{**v,"accuracy":v["correct"]/max(1,v["total"])} for c,v in per.items()}}
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("REAL_VISION_EVALUATION_OK",json.dumps(report),flush=True)

if __name__=="__main__":
    main()
