import asyncio
import io
import re
import sys
from contextlib import redirect_stdout, redirect_stderr
from functools import partial

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

from bot.config import SPOTIFY_CLIENT_ID, SPOTIFY_SECRET
from bot.spotify.throttle import throttle
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


# ─── CAPTURE STDOUT + STDERR ──────────────────────────────────────────────────
class _OutputCapture:
    """Capture stdout et stderr pour intercepter le Retry-After que spotipy
    affiche avant de lever l'exception (sans l'inclure dans l'objet exception)."""

    _PATTERN = re.compile(r"Retry will occur after:\s*(\d+)")

    def __init__(self):
        self._stdout_buf = io.StringIO()
        self._stderr_buf = io.StringIO()
        self.retry_after: int | None = None

    def __enter__(self):
        self._redir_out = redirect_stdout(self._stdout_buf)
        self._redir_err = redirect_stderr(self._stderr_buf)
        self._redir_out.__enter__()
        self._redir_err.__enter__()
        return self

    def parse(self):
        """Parse les buffers immédiatement — à appeler dans le bloc except,
        avant que __exit__ ne restaure les streams."""
        combined = self._stdout_buf.getvalue() + self._stderr_buf.getvalue()
        if combined.strip():
            log.debug(f"[spotipy output] {combined.strip()}")
        match = self._PATTERN.search(combined)
        if match:
            self.retry_after = int(match.group(1))

    def __exit__(self, *args):
        self._redir_err.__exit__(*args)
        self._redir_out.__exit__(*args)
        if self.retry_after is None:
            self.parse()


# ─── FONCTIONS SYNCHRONES UNITAIRES (exécutées dans un thread) ────────────────

def _get_artist_albums(artist_id: str, album_type: str) -> dict:
    """Un seul appel artist_albums — une requête API = un acquire."""
    with _OutputCapture() as cap:
        try:
            return sp.artist_albums(artist_id, album_type=album_type, limit=1)
        except SpotifyException as e:
            cap.parse()
            if cap.retry_after is not None:
                e._captured_retry_after = cap.retry_after
            raise


def _get_artist(artist_id: str) -> dict | None:
    """Récupère un artiste par son ID."""
    with _OutputCapture() as cap:
        try:
            return sp.artist(artist_id)
        except SpotifyException as e:
            cap.parse()
            if cap.retry_after is not None:
                e._captured_retry_after = cap.retry_after
            raise


# ─── WRAPPERS ASYNC ───────────────────────────────────────────────────────────

async def get_latest_release(artist_id: str, priority: bool = False) -> dict | None:
    """
    Récupère la dernière sortie d'un artiste (2 requêtes API throttlées).

    Args:
        priority: True pour les commandes utilisateur (/spy),
                  False pour le checker (défaut).
    """
    loop = asyncio.get_event_loop()
    try:
        # Requête 1 : albums + compilations
        await throttle.acquire(priority=priority)
        albums = await loop.run_in_executor(
            None, partial(_get_artist_albums, artist_id, "album,compilation")
        )

        # Requête 2 : singles
        await throttle.acquire(priority=priority)
        singles = await loop.run_in_executor(
            None, partial(_get_artist_albums, artist_id, "single")
        )

        # Fusionner et trier par date
        items = albums.get("items", []) + singles.get("items", [])
        if not items:
            log.debug(f"Dernière sortie pour {artist_id}: aucune")
            return None

        items.sort(key=lambda x: x.get("release_date", "0000"), reverse=True)
        result = items[0]
        log.debug(f"Dernière sortie pour {artist_id}: {result['name']}")
        return result

    except SpotifyException as e:
        log.error(f"SpotifyException ({artist_id}) | HTTP {e.http_status} | {e.msg} | {e.reason}")
        raise
    except Exception as e:
        log.error(f"Erreur inattendue ({artist_id}) | {type(e).__name__}: {e}")
        raise


async def get_artist_from_url(url: str, priority: bool = False) -> dict | None:
    """
    Récupère un artiste depuis son URL Spotify (1 requête API throttlée).

    Args:
        priority: True pour les commandes utilisateur (/spy),
                  False pour le checker (défaut).
    """
    artist_id = url.split("/artist/")[1].split("?")[0].split("/")[0]
    loop = asyncio.get_event_loop()
    try:
        await throttle.acquire(priority=priority)
        result = await loop.run_in_executor(None, partial(_get_artist, artist_id))
        if result:
            log.debug(f"Artiste trouvé : {result['name']} ({result['id']})")
        return result
    except SpotifyException as e:
        log.error(f"SpotifyException (url={url}) | HTTP {e.http_status} | {e.msg} | {e.reason}")
        raise
    except Exception as e:
        log.error(f"Erreur inattendue (url={url}) | {type(e).__name__}: {e}")
        raise