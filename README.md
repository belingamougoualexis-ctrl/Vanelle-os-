# Vanelle — AI Engineering & Training OS

Vanelle est un studio local-first pour importer, préparer, entraîner, évaluer et exporter des modèles d'IA avec les données et l'objectif de l'utilisateur.

## Ce que Vanelle fait réellement

- Chat local avec GGUF via llama.cpp.
- Import de modèles GGUF ou de dossiers Transformers contenant une configuration et des poids accessibles localement.
- Analyse du modèle : format, famille, architecture, taille et compatibilité du backend.
- Analyse de l'objectif, du dataset et du matériel afin de choisir une stratégie d'adaptation.
- Préparation/normalisation de datasets JSONL, JSON, CSV, TXT et Markdown.
- Entraînement LoRA/SFT réel : llama.cpp pour GGUF et Transformers + PEFT pour les modèles Transformers.
- Checkpoints et journaux réels d'entraînement.
- Evaluation par générations réelles sur des scénarios comportementaux.
- Analyse des échecs, génération de données correctives puis nouveau cycle d'entraînement.
- Chat post-entraînement avec l'adaptateur actif.
- Export d'un projet complet avec manifeste reproductible.
- Documents locaux, recherche, mémoire et conversations conservés localement.

## Comment Vanelle choisit le moteur

Vanelle ne prétend pas entraîner n'importe quel modèle avec n'importe quelle machine.

```text
Modèle importé
    ↓
Détection du format / architecture
    ↓
Objectif utilisateur
    ↓
Dataset disponible
    ↓
CPU / RAM / GPU / backend
    ↓
Plan d'entraînement
    ↓
Training réel
    ↓
Evaluation réelle
    ↓
Analyse des erreurs
    ↓
Corrections + nouveau cycle
```

Pour un GGUF, Vanelle utilise le moteur llama.cpp embarqué.

Pour un modèle Transformers, Vanelle utilise un moteur local Python basé sur Transformers + PEFT. Les poids doivent être accessibles sur la machine et le runtime Python correspondant doit être installé. L'application refuse de transformer un modèle inaccessible en faux entraînement.

## Utilisation par de grandes équipes IA

L'architecture est volontairement agnostique du fournisseur. Une équipe peut importer un modèle dont les poids et l'architecture d'entraînement sont légalement et techniquement accessibles, utiliser ses propres données, puis exporter :

- les données préparées ;
- la configuration du projet ;
- les checkpoints ;
- l'adaptateur ;
- le rapport d'évaluation ;
- `vanelle_project_manifest.json` ;
- un README de reproduction.

Cela permet d'intégrer Vanelle dans un environnement de recherche ou de production où l'organisation contrôle elle-même les modèles et les GPU.

Un modèle propriétaire fermé dont les poids, le tokenizer, l'architecture d'entraînement ou l'accès aux mécanismes de fine-tuning ne sont pas fournis ne peut pas être entraîné localement par Vanelle. Vanelle ne contourne pas ces restrictions.

## Validation sans simulation

Les workflows GitHub Actions téléchargent un vrai modèle ouvert et un vrai dataset public, exécutent un véritable entraînement LoRA, une génération réelle, une évaluation réelle et publient les rapports comme artefacts CI.

Le pipeline Windows construit également les exécutables Vanelle, le moteur CPU/Vulkan et effectue des tests de conversation et de LoRA avec de vrais fichiers GGUF.

## Structure

- `app/` — application Vanelle Tauri + React.
- `universal_engine/` — scripts locaux Transformers/PEFT.
- `scripts/` — construction Windows.
- `.github/workflows/` — validations réelles CI.