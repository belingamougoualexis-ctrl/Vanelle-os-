#!/usr/bin/env python3
import argparse, json, os, random
from pathlib import Path
from typing import List, Tuple

import torch
from torch import nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms
from torchvision.models import MobileNet_V3_Small_Weights

IMAGE_EXTS={".jpg",".jpeg",".png",".bmp",".webp",".tif",".tiff"}

def build_model(num_classes:int, pretrained:bool=True):
    weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--epochs",type=int,default=1)
    ap.add_argument("--batch-size",type=int,default=16)
    ap.add_argument("--image-size",type=int,default=224)
    ap.add_argument("--val-ratio",type=float,default=.2)
    ap.add_argument("--lr",type=float,default=1e-3)
    ap.add_argument("--seed",type=int,default=42)
    args=ap.parse_args()

    random.seed(args.seed); torch.manual_seed(args.seed)
    root=Path(args.dataset); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    if not root.is_dir(): raise SystemExit("Dataset vision introuvable.")
    classes=sorted([p.name for p in root.iterdir() if p.is_dir()])
    if len(classes)<2: raise SystemExit("Le dataset doit contenir au moins deux classes (un dossier par classe).")
    for c in classes:
        if not any(p.is_file() and p.suffix.lower() in IMAGE_EXTS for p in (root/c).rglob("*")):
            raise SystemExit(f"Classe sans image: {c}")

    weights=MobileNet_V3_Small_Weights.DEFAULT
    train_tf=transforms.Compose([
        transforms.RandomResizedCrop(args.image_size,scale=(.75,1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
    ])
    val_tf=transforms.Compose([
        transforms.Resize((args.image_size,args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(weights.meta["mean"],weights.meta["std"])
    ])

    base=datasets.ImageFolder(root, transform=train_tf)
    if len(base)<max(10,len(classes)*2): raise SystemExit(f"Dataset trop petit: {len(base)} images.")
    val_n=max(len(classes), int(round(len(base)*args.val_ratio)))
    train_n=len(base)-val_n
    train_ds,val_ds=random_split(base,[train_n,val_n],generator=torch.Generator().manual_seed(args.seed))
    val_ds.dataset.transform=val_tf
    train_dl=DataLoader(train_ds,batch_size=args.batch_size,shuffle=True,num_workers=0)
    val_dl=DataLoader(val_ds,batch_size=args.batch_size,shuffle=False,num_workers=0)

    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model=build_model(len(classes),pretrained=True).to(device)
    for p in model.features.parameters(): p.requires_grad=False
    criterion=nn.CrossEntropyLoss()
    opt=torch.optim.AdamW(model.classifier.parameters(),lr=args.lr)

    best_acc=-1.0
    history=[]
    for epoch in range(1,args.epochs+1):
        model.train(); seen=correct=0; loss_sum=0.0
        for x,y in train_dl:
            x,y=x.to(device),y.to(device)
            opt.zero_grad(set_to_none=True)
            logits=model(x); loss=criterion(logits,y); loss.backward(); opt.step()
            loss_sum += float(loss.item())*len(y); seen += len(y); correct += int((logits.argmax(1)==y).sum())
        model.eval(); vseen=vcorr=0; vloss=0.0
        with torch.no_grad():
            for x,y in val_dl:
                x,y=x.to(device),y.to(device); logits=model(x); loss=criterion(logits,y)
                vloss += float(loss.item())*len(y); vseen += len(y); vcorr += int((logits.argmax(1)==y).sum())
        train_acc=correct/max(1,seen); val_acc=vcorr/max(1,vseen)
        row={"epoch":epoch,"train_loss":loss_sum/max(1,seen),"train_accuracy":train_acc,
             "val_loss":vloss/max(1,vseen),"val_accuracy":val_acc}
        history.append(row)
        print(json.dumps(row),flush=True)
        if val_acc>best_acc:
            best_acc=val_acc
            torch.save({"state_dict":model.state_dict(),"classes":classes,"image_size":args.image_size,
                        "mean":list(weights.meta["mean"]),"std":list(weights.meta["std"]),
                        "architecture":"mobilenet_v3_small","num_classes":len(classes)},out/"best.pt")
    summary={"format":"vision-classifier","architecture":"mobilenet_v3_small","classes":classes,
             "num_classes":len(classes),"images":len(base),"train_images":train_n,"val_images":val_n,
             "best_val_accuracy":best_acc,"device":str(device),"history":history,
             "weights":"MobileNet_V3_Small_Weights.DEFAULT"}
    (out/"training_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (out/"classes.json").write_text(json.dumps(classes,ensure_ascii=False,indent=2),encoding="utf-8")
    print("REAL_VISION_TRAINING_OK",json.dumps(summary),flush=True)

if __name__=="__main__":
    main()
