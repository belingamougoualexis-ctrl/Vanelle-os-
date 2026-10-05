#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torch import nn

def load(checkpoint,device):
    ck=torch.load(checkpoint,map_location=device)
    classes=ck["classes"]
    model=models.mobilenet_v3_small(weights=None)
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,len(classes))
    model.load_state_dict(ck["state_dict"])
    model.to(device).eval()
    return model,classes,ck

def main():
    ap=argparse.ArgumentParser(description="Test-only vision benchmark; never trains or modifies the model.")
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--checkpoint",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--batch-size",type=int,default=16)
    args=ap.parse_args()
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model,classes,ck=load(args.checkpoint,device)
    tf=transforms.Compose([transforms.Resize((ck["image_size"],ck["image_size"])),
                           transforms.ToTensor(),transforms.Normalize(ck["mean"],ck["std"])])
    ds=datasets.ImageFolder(args.dataset,transform=tf)
    if ds.class_to_idx != {c:i for i,c in enumerate(classes)}:
        raise SystemExit(f"Classes du benchmark incompatibles avec le modèle: dataset={ds.classes}, model={classes}")
    loader=DataLoader(ds,batch_size=args.batch_size,shuffle=False,num_workers=0)
    confusion=[[0 for _ in classes] for __ in classes]
    errors=[]; total=correct=high_conf_wrong=low_conf_correct=0
    with torch.no_grad():
        offset=0
        for x,y in loader:
            probs=torch.softmax(model(x.to(device)),dim=1)
            vals,pred=probs.max(1)
            for i,(yi,pi,conf) in enumerate(zip(y.tolist(),pred.tolist(),vals.tolist())):
                path, _ = ds.samples[offset+i]
                actual=classes[yi]; predicted=classes[pi]
                confusion[yi][pi]+=1; total+=1
                if yi==pi:
                    correct+=1
                    if conf<0.60: low_conf_correct+=1
                else:
                    item={"image":str(Path(path).relative_to(Path(args.dataset))),"actual":actual,
                          "predicted":predicted,"confidence":float(conf)}
                    errors.append(item)
                    if conf>=0.80: high_conf_wrong+=1
            offset += len(y)
    per={}
    for i,c in enumerate(classes):
        support=sum(confusion[i])
        tp=confusion[i][i]
        predicted_total=sum(confusion[r][i] for r in range(len(classes)))
        precision=tp/max(1,predicted_total); recall=tp/max(1,support)
        per[c]={"correct":tp,"total":support,"accuracy":recall,"precision":precision}
    accuracy=correct/max(1,total)
    report={"format":"vision-test-only","training_performed":False,"modified_model":False,
            "images":total,"correct":correct,"errors":len(errors),"accuracy":accuracy,
            "high_confidence_errors":high_conf_wrong,"low_confidence_correct":low_conf_correct,
            "classes":classes,"confusion_matrix":confusion,"per_class":per,
            "errors":errors,"device":str(device)}
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("VISION_TEST_ONLY_OK",json.dumps(report),flush=True)

if __name__=="__main__":
    main()
