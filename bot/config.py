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

# ─── PATHS & SETTINGS ─────────────────────────────────────────────────────────
DATA_FILE          = "tracked.json"
CHECK_INTERVAL_H   = 1        # intervalle de vérification en heures
STARTUP_DELAY_S    = 10       # délai avant le premier cycle en secondes
LOG_FILE           = "bot.log"