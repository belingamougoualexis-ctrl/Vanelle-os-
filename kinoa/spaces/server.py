from pathlib import Path
import os, sys
sys.path.insert(0,"/app")
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from backend.app.hardware import detect_hardware, wan22_readiness
from backend.app.video_engine import get_video_engine

app=FastAPI(title="KINOA GPU Runtime")
@app.get("/health")
def health():
    h=detect_hardware()
    return JSONResponse({"status":"ok","hardware":h,"wan22":wan22_readiness(h)})
@app.get("/engine")
def engine():
    return get_video_engine().readiness()

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=7860)
