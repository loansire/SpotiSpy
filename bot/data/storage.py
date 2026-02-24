import json
import os
from bot.config import DATA_FILE
from bot.utils.logger import log


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            guild_count  = len(data)
            artist_count = sum(len(a) for a in data.values())
            log.info(f"Données chargées : {guild_count} guild(s), {artist_count} artiste(s)")
            return data
    log.warning(f"Fichier '{DATA_FILE}' introuvable, démarrage à vide")
    return {}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug("Données sauvegardées")


def get_guild(guild_id: int) -> dict:
    """Retourne le dict d'artistes pour un guild, le crée si inexistant."""
    key = str(guild_id)
    if key not in tracked:
        tracked[key] = {}
    return tracked[key]


def _extract_image(artist: dict) -> str | None:
    """Extrait la plus petite image de profil d'un artiste Spotify."""
    images = artist.get("images", [])
    if not images:
        return None
    # Trier par taille croissante, prendre la plus petite (160px en général)
    sorted_imgs = sorted(images, key=lambda x: x.get("height", 0))
    return sorted_imgs[0]["url"]


def add_artist(guild_id: int, artist: dict, release: dict | None, notify_role: bool, user_id: int | None) -> bool:
    """
    Ajoute un artiste dans un guild ou met à jour notify_role s'il existe déjà.
    Retourne True si l'artiste a été créé, False s'il existait déjà.
    """
    guild_data = get_guild(guild_id)
    aid  = artist["id"]
    name = artist["name"]
    image = _extract_image(artist)

    if aid in guild_data:
        if notify_role and not guild_data[aid].get("notify_role"):
            guild_data[aid]["notify_role"] = True
            save_data(tracked)
        if user_id and user_id not in guild_data[aid].setdefault("subscribers", []):
            guild_data[aid]["subscribers"].append(user_id)
            save_data(tracked)
        # Mettre à jour l'image si absente
        if image and not guild_data[aid].get("image_url"):
            guild_data[aid]["image_url"] = image
            save_data(tracked)
        return False

    guild_data[aid] = {
        "name":              name,
        "image_url":         image,
        "last_release_id":   release["id"] if release else None,
        "last_release_name": release["name"] if release else None,
        "last_release_url":  release["external_urls"]["spotify"] if release else None,
        "subscribers":       [user_id] if user_id else [],
        "notify_role":       notify_role
    }
    save_data(tracked)
    return True


def cleanup_artist(guild_id: int, artist_id: str):
    """Supprime un artiste s'il n'a plus d'abonnés ni de notify_role. Supprime le guild s'il est vide."""
    gid = str(guild_id)
    if gid not in tracked or artist_id not in tracked[gid]:
        return

    info = tracked[gid][artist_id]
    if not info.get("subscribers") and not info.get("notify_role"):
        del tracked[gid][artist_id]
        if not tracked[gid]:
            del tracked[gid]
        save_data(tracked)
        log.info(f"[Guild {gid}] Artiste supprimé (plus d'abonnés ni de ping rôle) : {info['name']}")


# Dictionnaire partagé, chargé une seule fois au démarrage
tracked: dict = load_data()