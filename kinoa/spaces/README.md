---
title: KINOA AI FILM STUDIO
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# KINOA GPU Space

This Space is the optional GPU execution target for KINOA's real video engine. It must never report successful generation unless a compatible CUDA runtime and model are actually available.

Configure GPU hardware in the Space settings. Docker Spaces support GPU hardware; build steps must not execute GPU checks because GPU hardware is only available at runtime. See Hugging Face's Spaces documentation.
