# Vanelle

Vanelle est un studio local d'ingénierie IA pour travailler à partir d'un modèle et de données appartenant à l'utilisateur.

## Fonctionnalités

- Chat local avec modèle GGUF et llama.cpp.
- Import et recherche de documents locaux.
- Mémoire et conversations locales.
- Création de projets avec un objectif explicite.
- Import et normalisation de datasets JSONL, JSON, CSV, TXT et Markdown.
- Analyse du modèle, des contraintes matérielles et de l'objectif.
- Entraînement LoRA/SFT local avec checkpoints.
- Application d'un adaptateur LoRA au modèle pour les tests.
- Scénarios d'évaluation comportementale.
- Enrichissement du dataset à partir des échecs détectés.
- Export d'un projet complet en ZIP.

## Principe

Vanelle ne prétend pas pouvoir entraîner n'importe quel modèle sur n'importe quelle machine. L'Advisor calcule une configuration à partir de la taille réelle du modèle, du type de modèle détecté, de l'objectif et des capacités matérielles disponibles. L'entraînement est ensuite exécuté par un moteur local réel, pas par une simulation.

## Moteur d'entraînement

Le pipeline Windows embarque un moteur basé sur le fork qvac-fabric-llm.cpp qui fournit le binaire de fine-tuning LoRA ainsi que les outils d'inférence, d'export et de perplexité. Les binaires sont construits dans GitHub Actions à partir du dépôt du moteur au moment de chaque release.

## Limites importantes

L'entraînement demande des ressources matérielles réelles. Les modèles volumineux peuvent dépasser la RAM/VRAM disponible. L'interface affiche les contraintes détectées afin d'éviter de lancer aveuglément un entraînement impossible.

