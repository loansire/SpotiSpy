from dotenv import load_dotenv
import os

load_dotenv()

# ─── TOKENS & CREDENTIALS ─────────────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID  = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET     = os.getenv("SPOTIFY_SECRET")

# ─── DISCORD IDS ───────────────────────────────────────────────────────────────
ANNOUNCE_CHANNEL   = int(os.getenv("ANNOUNCE_CHANNEL", 0))

# ─── PATHS & SETTINGS ─────────────────────────────────────────────────────────
DATA_FILE          = "tracked.json"
QUEUE_FILE                = "queue.json"
RATE_LIMIT_PING_INTERVAL  = 600    #600 secondes entre les logs de progression du rate limit
QUEUE_REQUEST_DELAY       = 2      # secondes entre chaque requête lors du traitement de la file
CHECK_INTERVAL_H   = 1        # intervalle de vérification en heures
STARTUP_DELAY_S    = 5       # délai avant le premier cycle en secondes
LOG_FILE           = "bot.log"

# ─── THROTTLE PROACTIF ─────────────────────────────────────────────────────────
THROTTLE_WINDOW_S       = 30     # fenêtre glissante Spotify (secondes)
THROTTLE_MAX_REQUESTS   = 25     # limite conservatrice (à calibrer en prod)
THROTTLE_RESERVED_SLOTS = 3      # slots réservés aux commandes utilisateur (/spy)
# Delay calculé automatiquement : WINDOW / (MAX - RESERVED) = 30/22 ≈ 1.36s entre chaque requête