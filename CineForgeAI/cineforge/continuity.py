def validate_story(story):
    """Return actionable continuity warnings without inventing or silently rewriting content."""
    warnings = []
    characters = story.get("characters", [])
    names = {str(c.get("name", "")).strip() for c in characters if isinstance(c, dict)}
    scenes = story.get("scenes", [])
    seen_numbers = set()
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            warnings.append(f"Scène {index}: structure invalide.")
            continue
        number = scene.get("number", index)
        if number in seen_numbers:
            warnings.append(f"Scène {index}: numéro {number} en double.")
        seen_numbers.add(number)
        if not str(scene.get("action", "")).strip() and not str(scene.get("video_prompt", "")).strip():
            warnings.append(f"Scène {number}: action et prompt vidéo sont vides.")
        try:
            if int(scene.get("duration_seconds", 0)) <= 0:
                warnings.append(f"Scène {number}: durée non positive.")
        except (TypeError, ValueError):
            warnings.append(f"Scène {number}: durée invalide.")
        for name in scene.get("characters", []) or []:
            if name not in names:
                warnings.append(f"Scène {number}: personnage « {name} » absent de la bible des personnages.")
    if not scenes:
        warnings.append("Le scénario ne contient aucune scène.")
    if not story.get("synopsis"):
        warnings.append("Synopsis absent : vérifie que l'histoire possède un arc narratif complet.")
    return warnings
