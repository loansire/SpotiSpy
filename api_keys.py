from dotenv import load_dotenv
import os

load_dotenv()

class ApiKey:
    discord           = os.getenv("DISCORD_TOKEN")
    spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
    spotify_secret    = os.getenv("SPOTIFY_SECRET")