from dotenv import load_dotenv
import os

load_dotenv()

# ─── TOKENS & CREDENTIALS ─────────────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID  = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET     = os.getenv("SPOTIFY_SECRET")

# ─── DISCORD IDS ───────────────────────────────────────────────────────────────
ANNOUNCE_CHANNEL   = int(os.getenv("ANNOUNCE_CHANNEL", 0))
NOTIFY_ROLE_ID     = int(os.getenv("NOTIFY_ROLE_ID", 0))
ADMIN_ROLE_ID      = int(os.getenv("ADMIN_ROLE_ID", 0))

# ─── PATHS & SETTINGS ─────────────────────────────────────────────────────────
DATA_FILE          = "tracked.json"
QUEUE_FILE                = "queue.json"
RATE_LIMIT_PING_INTERVAL  = 3    #600 secondes entre les logs de progression du rate limit
QUEUE_REQUEST_DELAY       = 2      # secondes entre chaque requête lors du traitement de la file
CHECK_INTERVAL_H   = 1        # intervalle de vérification en heures
STARTUP_DELAY_S    = 10       # délai avant le premier cycle en secondes
LOG_FILE           = "bot.log"
SLEEP_THRESHOLD    = 10      # nb d'artistes à partir duquel on active le délai entre requêtes