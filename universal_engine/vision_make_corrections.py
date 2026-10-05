#!/usr/bin/env python3
import argparse, json, shutil
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--report",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    root=Path(args.dataset); report=json.loads(Path(args.report).read_text(encoding="utf-8")); out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    created=0
    for idx,item in enumerate(report.get("errors",[])):
        src=root/item["image"]; actual=item["actual"]
        if not src.is_file(): continue
        dest_dir=out/actual; dest_dir.mkdir(parents=True,exist_ok=True)
        dest=dest_dir/f"correction-{idx:05d}-{src.name}"
        shutil.copy2(src,dest); created+=1
    manifest={"format":"vision-corrections","source_test_report":str(Path(args.report).name),
              "images":created,"classes":report.get("classes",[]),
              "warning":"Ces images proviennent d'un benchmark de test. Pour une mesure post-amélioration non biaisée, utilisez un nouveau benchmark indépendant."}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print("VISION_CORRECTIONS_OK",json.dumps(manifest),flush=True)

if __name__=="__main__":
    main()
