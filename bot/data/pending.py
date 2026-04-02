"""Gestion de la file d'attente des requêtes pendant un rate limit Spotify."""

import json
import os
from datetime import datetime, timezone

from bot.config import QUEUE_FILE
from bot.utils.logger import log


def load_queue() -> list[dict]:
    """Charge la file d'attente depuis queue.json."""
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            log.info(f"File d'attente chargée : {len(data)} requête(s) en attente")
            return data
    return []


def save_queue():
    """Sauvegarde la file d'attente dans queue.json."""
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    log.debug(f"File d'attente sauvegardée ({len(queue)} élément(s))")


def _normalize_url(url: str) -> str:
    """Extrait l'artist ID d'une URL Spotify pour comparaison fiable."""
    try:
        return url.split("/artist/")[1].split("?")[0].split("/")[0]
    except (IndexError, AttributeError):
        return url


def is_duplicate(guild_id: int, url: str) -> bool:
    """Vérifie si une requête identique (même guild + même artiste) est déjà en file."""
    artist_id = _normalize_url(url)
    for entry in queue:
        if entry["guild_id"] == guild_id and _normalize_url(entry["url"]) == artist_id:
            return True
    return False


def add_to_queue(guild_id: int, user_id: int, url: str) -> bool:
    """
    Ajoute une requête à la file d'attente.
    Retourne True si ajoutée, False si doublon détecté.
    """
    if is_duplicate(guild_id, url):
        log.debug(f"Doublon détecté dans la file : guild={guild_id}, url={url}")
        return False

    entry = {
        "guild_id": guild_id,
        "user_id": user_id,
        "url": url,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    queue.append(entry)
    save_queue()
    log.info(f"Requête ajoutée à la file : guild={guild_id}, user={user_id}, url={url}")
    return True


def remove_entry(entry: dict):
    """Retire une entrée de la file et sauvegarde."""
    try:
        queue.remove(entry)
        save_queue()
    except ValueError:
        pass


# File d'attente partagée, chargée une seule fois au démarrage
queue: list[dict] = load_queue()