import json
import os
from bot.config import DATA_FILE
from bot.utils.logger import log


def load_data() -> dict:
    """Charge les données depuis le fichier JSON.
    Structure : { guild_id: { artist_id: { ...info } } }
    """
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            guild_count  = len(data)
            artist_count = sum(len(artists) for artists in data.values())
            log.info(f"Données chargées : {guild_count} guild(s), {artist_count} artiste(s)")
            return data
    log.warning(f"Fichier '{DATA_FILE}' introuvable, démarrage à vide")
    return {}


def save_data(data: dict):
    """Sauvegarde les données dans le fichier JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug(f"Données sauvegardées")


def get_guild(guild_id: int) -> dict:
    """Retourne le dict d'artistes pour un guild, le crée si inexistant."""
    key = str(guild_id)
    if key not in tracked:
        tracked[key] = {}
    return tracked[key]


# Dictionnaire partagé, chargé une seule fois au démarrage
tracked: dict = load_data()