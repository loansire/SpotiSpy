import json
import os
from bot.config import DATA_FILE
from bot.utils.logger import log


def load_data() -> dict:
    """Charge les artistes suivis depuis le fichier JSON."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            log.info(f"Données chargées : {len(data)} artiste(s)")
            return data
    log.warning(f"Fichier '{DATA_FILE}' introuvable, démarrage à vide")
    return {}


def save_data(data: dict):
    """Sauvegarde les artistes suivis dans le fichier JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug(f"Données sauvegardées ({len(data)} artiste(s))")


# Dictionnaire partagé, chargé une seule fois au démarrage
tracked: dict = load_data()