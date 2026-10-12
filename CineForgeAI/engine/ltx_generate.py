import argparse
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True); p.add_argument("--output", required=True)
    p.add_argument("--seconds", type=int, default=5); p.add_argument("--width", type=int, default=768)
    p.add_argument("--height", type=int, default=512); p.add_argument("--fps", type=int, default=24)
    p.add_argument("--model", default="Lightricks/LTX-2.5-Diffusers")
    a = p.parse_args()
    if not a.prompt.strip(): raise SystemExit("Prompt vide.")
    try:
        import torch
        from diffusers import LTX2Pipeline
        from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES
        from diffusers.utils import encode_video
    except Exception as exc:
        raise SystemExit(f"Dépendances LTX absentes/incompatibles. Installe PyTorch adapté puis requirements-video.txt. Détail: {exc}")
    device = "cuda" if torch.cuda.is_available() else ("mps" if hasattr(torch.backends,"mps") and torch.backends.mps.is_available() else "cpu")
    dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else (torch.float16 if device != "cpu" else torch.float32)
    if device == "cpu": print("AVERTISSEMENT: inférence CPU potentiellement extrêmement lente et gourmande en RAM.")
    frames = max(9, min(241, a.seconds*a.fps+1)); frames = ((frames-1+7)//8)*8+1; frames=min(frames,241)
    output = Path(a.output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    print(f"Chargement réel de {a.model} sur {device}; Hugging Face téléchargera les poids manquants.")
    pipe = LTX2Pipeline.from_pretrained(a.model, dtype=dtype)
    if device == "cuda": pipe.enable_sequential_cpu_offload(device=device)
    else: pipe.to(device)
    if hasattr(pipe.vae,"enable_tiling"): pipe.vae.enable_tiling()
    gen = torch.Generator(device=device).manual_seed(42)
    video, audio = pipe(prompt=a.prompt, width=a.width, height=a.height, num_frames=frames, frame_rate=float(a.fps),
        sigmas=DISTILLED_SIGMA_VALUES, guidance_scale=1.0, audio_guidance_scale=1.0, generator=gen,
        output_type="np", return_dict=False)
    encode_video(video[0], fps=a.fps, audio=audio[0].float().cpu(),
        audio_sample_rate=pipe.vocoder.config.output_sampling_rate, output_path=str(output))
    if not output.exists() or output.stat().st_size == 0: raise SystemExit("Le moteur n'a produit aucun MP4.")
    print(f"SUCCESS {output} ({output.stat().st_size} octets)")

if __name__ == "__main__": main()
