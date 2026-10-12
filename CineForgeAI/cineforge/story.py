import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SYSTEM = """Tu es scénariste de cinéma et script-doctor. Développe l'idée en une histoire complète avec début, milieu,
fin, objectifs, conflits, conséquences, rebondissements crédibles et dénouement satisfaisant. Préserve l'intention
de l'auteur. Assure la continuité des visages, âges, vêtements, accessoires, lieux, météo et chronologie.
Direction visuelle live-action naturaliste : texture de peau visible, petites asymétries, gestes crédibles,
décors habités et éclairage motivé; éviter les visages lisses de mannequin et les environnements artificiellement parfaits.
Réponds uniquement par un JSON valide avec title, logline, synopsis, characters et scenes. Chaque personnage:
name, age, appearance, personality, goal, voice. Chaque scène: number, title, location, time, characters (liste),
action, dialogue, camera, lighting, sound, continuity, duration_seconds, video_prompt. Les scènes doivent raconter
une histoire complète et les durées être positives."""

def complete_story(premise, model="qwen3:4b", genre="Drame", duration_minutes=3, language="français"):
    if not premise.strip():
        raise ValueError("Écris une idée de départ.")
    payload = {"model": model, "stream": False, "format": "json",
        "messages": [{"role":"system","content":SYSTEM},
        {"role":"user","content":f"Idee: {premise}\nGenre: {genre}\nDurée cible: {duration_minutes} minutes.\nLangue: {language}. Complète toute l'histoire et découpe-la en scènes réalisables."}],
        "options":{"temperature":0.7,"num_ctx":8192}}
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as res:
            raw = json.loads(res.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama local inaccessible. Installe Ollama, télécharge un modèle local et démarre le service. Aucun cloud n'a été utilisé.") from exc
    try:
        result = json.loads(raw.get("message",{}).get("content",""))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Le modèle local n'a pas renvoyé de JSON valide; essaie une consigne plus courte.") from exc
    scenes = result.get("scenes")
    if not isinstance(scenes,list) or not scenes:
        raise RuntimeError("Aucune scène exploitable n'a été créée.")
    for i, scene in enumerate(scenes, 1):
        scene["number"] = int(scene.get("number") or i)
        scene["duration_seconds"] = max(1, int(scene.get("duration_seconds") or 5))
        scene.setdefault("video_prompt", scene.get("action",""))
        scene.setdefault("continuity","")
    return result
