# KINOA — AI FILM STUDIO

KINOA est développé sur la branche `kinoa` de Vanelle-os- comme une architecture de production réelle, sans génération vidéo simulée.

## Architecture
- `backend/`: API FastAPI, projets, Film Bible, checkpoints et contrat moteur vidéo.
- `web/`: interface studio responsive.
- `engine.py`: abstraction de moteur et adaptateur Wan2.2 T2V-A14B.
- `.github/workflows/kinoa-ci.yml`: validation automatisée.

## Vérité de génération
Le moteur Wan2.2 ne produit aucun faux fichier. Si le runtime ou le GPU ne sont pas disponibles, la génération échoue explicitement avec une cause vérifiable.

## Lancer l'API
```bash
cd kinoa/backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Tests
`pytest -q` dans `kinoa/backend`.
