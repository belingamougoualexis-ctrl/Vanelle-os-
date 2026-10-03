# Alpha Prime 2.1.1 — GitHub release validation

This repository contains the Alpha Prime 2.1.1 release validation bundle.

The source archive is stored as base64 parts under alphaprime_release/bundle.parts/. GitHub Actions reconstructs the exact archive, verifies SHA-256, extracts it, runs desktop tests, performs the mobile quality/build path, and can run a Hugging Face GPU matrix.

Expected archive SHA-256:
51b9bd2a06f4e8e743dbacc86ec3a1dcb0f4f758f7f8b329ef7fc00e4b1b2bf5

Current documented Hugging Face GPU flavors covered by the matrix: T4, L4, L40S, A10G and A100 variants. H100 is excluded because Hugging Face documents it as removed from the current hardware list.

The Hugging Face workflow is manual because it uses paid cloud compute and requires the repository secret HF_TOKEN.
