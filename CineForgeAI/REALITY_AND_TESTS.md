# Réalité et tests

- Projet local JSON : sauvegarde/chargement implémentés.
- Complétion d'histoire : requête vers Ollama local uniquement, JSON vérifié.
- Génération vidéo : adaptateur Diffusers/LTX-2.5; dépendances et poids ne sont pas inclus.
- Export : FFmpeg valide la présence des clips et l'existence du MP4 final.
- Aucun rendu de substitution n'est produit si le modèle échoue.
- Tests unitaires et compilation source : automatisés par GitHub Actions.
- L'inférence GPU réelle, la qualité multi-scène et la lecture sur un PC cible doivent être testées sur la machine possédant les poids et le matériel compatibles.
- Vérifier la licence LTX avant publication commerciale.
