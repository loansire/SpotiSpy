"""
Script one-shot pour ajouter image_url aux artistes existants.
Lancer une seule fois : python migrate_images.py
"""

import json
from bot.config import DATA_FILE
from bot.spotify.api import sp


def migrate():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for gid, artists in data.items():
        for aid, info in artists.items():
            if info.get("image_url"):
                print(f"  ✓ {info['name']} — image déjà présente")
                continue

            try:
                artist = sp.artist(aid)
                images = artist.get("images", [])
                if images:
                    img = sorted(images, key=lambda x: x.get("height", 0))[0]["url"]
                    info["image_url"] = img
                    count += 1
                    print(f"  ✅ {info['name']} — image ajoutée")
                else:
                    info["image_url"] = None
                    print(f"  ⚠️ {info['name']} — pas d'image sur Spotify")
            except Exception as e:
                print(f"  ❌ {info['name']} — erreur : {e}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nTerminé — {count} image(s) ajoutée(s)")


if __name__ == "__main__":
    migrate()