import asyncio
from functools import partial

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

from bot.config import SPOTIFY_CLIENT_ID, SPOTIFY_SECRET
from bot.utils.logger import log

# ─── CLIENT SPOTIFY ────────────────────────────────────────────────────────────
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_SECRET,
        cache_handler=spotipy.MemoryCacheHandler()
    ),
    retries=0,
    backoff_factor=0
)


# ─── FONCTIONS SYNCHRONES (exécutées dans un thread) ──────────────────────────
def _get_latest_release(artist_id: str) -> dict | None:
    albums = sp.artist_albums(artist_id, album_type="album,compilation", limit=1)
    singles = sp.artist_albums(artist_id, album_type="single", limit=1)

    items = albums.get("items", []) + singles.get("items", [])
    if not items:
        return None
    items.sort(key=lambda x: x.get("release_date", "0000"), reverse=True)
    return items[0]


def _get_artist_from_url(url: str) -> dict | None:
    artist_id = url.split("/artist/")[1].split("?")[0].split("/")[0]
    return sp.artist(artist_id)


# ─── WRAPPERS ASYNC ───────────────────────────────────────────────────────────
async def get_latest_release(artist_id: str) -> dict | None:
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, partial(_get_latest_release, artist_id))
        log.debug(f"Dernière sortie pour {artist_id}: {result['name'] if result else 'aucune'}")
        return result
    except SpotifyException as e:
        log.error(f"SpotifyException ({artist_id}) | HTTP {e.http_status} | {e.msg} | {e.reason}")
        raise
    except Exception as e:
        log.error(f"Erreur inattendue ({artist_id}) | {type(e).__name__}: {e}")
        raise


async def get_artist_from_url(url: str) -> dict | None:
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, partial(_get_artist_from_url, url))
        if result:
            log.debug(f"Artiste trouvé : {result['name']} ({result['id']})")
        return result
    except SpotifyException as e:
        log.error(f"SpotifyException (url={url}) | HTTP {e.http_status} | {e.msg} | {e.reason}")
        raise
    except Exception as e:
        log.error(f"Erreur inattendue (url={url}) | {type(e).__name__}: {e}")
        raise