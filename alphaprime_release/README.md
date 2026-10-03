# Alpha Prime — validation harness

Version tested locally: 2.1.1.

Local verification completed on the delivered source archive:
- 24 desktop pytest files exercised individually
- 88 tests passed
- 1 explicit skip
- full local E2E completed with REAL status
- human Safety Gate approval and local deployment path verified
- mobile UI/runtime hardening included in the delivered archive

Hugging Face GPU matrix:
T4, L4, L40S, A10G, A100, H200 and RTX PRO 6000 flavors, including the current documented multi-GPU variants.

The GPU workflow is manual because Hugging Face Jobs consumes paid compute and requires HF_TOKEN. It runs a real CUDA matrix multiply and real SmolLM2-360M-Instruct inference on each selected flavor.

Important: no GPU result is marked PASS until the corresponding Hugging Face job actually executes.