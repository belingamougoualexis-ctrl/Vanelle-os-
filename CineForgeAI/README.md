# CineForge AI Studio

Nouveau projet indépendant de Kinoa : studio Windows x64 pour développer une histoire, la découper en scènes, générer de vrais plans vidéo avec un modèle local et assembler les clips en MP4.

## Fonctions
- Scénario complet à partir d'une idée courte : personnages, motivations, actes, rebondissements, fin et continuité.
- Scénario généré par un modèle de texte local via Ollama (pas d'API de génération de texte distante).
- Gestion des scènes, prompts cinématographiques et sauvegarde locale JSON.
- Adaptateur d'inférence vidéo LTX-2.5 via Diffusers.
- Assemblage de clips réellement générés via FFmpeg.
- Tests et build Windows x64 via GitHub Actions.
- Aucun rendu fictif : si modèle/dépendances/FFmpeg manquent, l'application signale l'erreur.

## Installation Windows 10/11 x64
1. Installer Python 3.11 x64 et FFmpeg, puis ajouter FFmpeg au PATH.
2. Installer Ollama, puis lancer `ollama pull qwen3:4b`. L'application utilise l'API locale `127.0.0.1:11434`.
3. Lancer `install_windows.bat`, puis `run_windows.bat`.
4. Pour la vidéo IA, installer une version PyTorch adaptée au GPU depuis https://pytorch.org/get-started/locally/, puis `pip install -r requirements-video.txt`.
5. Sélectionner une scène et accepter explicitement le chargement/téléchargement des poids LTX avant de lancer une génération.

## Limites honnêtes
Les poids vidéo ne sont pas inclus dans Git : ils sont très volumineux. LTX-2.5 est un modèle conséquent, donc la compatibilité et la vitesse dépendent du GPU, de la VRAM et de la RAM. Un build CI Windows ne prouve pas une inférence GPU. Les longs films se construisent plan par plan; une génération parfaite d'un long métrage en une passe n'est pas garantie.

## Modèles et licence
- Vidéo/audio : https://huggingface.co/Lightricks/LTX-2.5-Diffusers
- Docs Diffusers : https://huggingface.co/docs/diffusers/main/en/api/pipelines/ltx2
- Texte local : https://ollama.com/library/qwen3

Vérifier la licence LTX-2.x Community License et les conditions commerciales actuelles avant toute distribution commerciale.

## Tests
`python -m unittest discover -s tests -v`

## Build
Le workflow `.github/workflows/windows-build.yml` exécute les tests et publie l'application Windows x64 en artefact GitHub Actions.
