# /// script
# dependencies = ["torch", "transformers"]
# ///
import json, socket, time
import torch
from transformers import pipeline

print("ALPHAPRIME_HF_PROBE=1")
print("HOSTNAME=", socket.gethostname())
print("CUDA_AVAILABLE=", torch.cuda.is_available())
print("CUDA_VERSION=", torch.version.cuda)
print("GPU_COUNT=", torch.cuda.device_count())
if not torch.cuda.is_available(): raise SystemExit("CUDA unavailable")

for i in range(torch.cuda.device_count()):
    p=torch.cuda.get_device_properties(i)
    print(json.dumps({"index":i,"name":torch.cuda.get_device_name(i),"memory_bytes":p.total_memory,"major":p.major,"minor":p.minor},ensure_ascii=False))

a=torch.randn((2048,2048),device="cuda",dtype=torch.float16)
b=torch.randn((2048,2048),device="cuda",dtype=torch.float16)
t0=time.perf_counter()
for _ in range(8): c=a@b
torch.cuda.synchronize()
print("MATMUL_MS=",round((time.perf_counter()-t0)*1000/8,2))
print("MATMUL_FINITE=",bool(torch.isfinite(c).all().item()))

generator=pipeline("text-generation",model="HuggingFaceTB/SmolLM2-360M-Instruct",device=0,dtype=torch.float16)
t0=time.perf_counter()
out=generator("Reply exactly: Alpha Prime GPU OK",max_new_tokens=16,do_sample=False)
torch.cuda.synchronize()
print("INFERENCE_SECONDS=",round(time.perf_counter()-t0,3))
print("MODEL_OUTPUT=",out[0]["generated_text"])