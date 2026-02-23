import discord
from discord import app_commands
from discord.ext import commands, tasks
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
import json
import os
import asyncio
from functools import partial
import requests
from requests.adapters import HTTPAdapter

from api_keys import ApiKey

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN      = ApiKey.discord
SPOTIFY_CLIENT_ID  = ApiKey.spotify_client_id
SPOTIFY_SECRET     = ApiKey.spotify_secret
ANNOUNCE_CHANNEL   = 1475028867604549683
NOTIFY_ROLE_ID     = 1475030252911853669
DATA_FILE          = "tracked.json"
# ───────────────────────────────────────────────────────────────────────────────

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_SECRET
    ),
    retries=1  # 1 = pas de retry (spotipy: 0 = infini, 1 = aucun retry)
)

# Remplace l'adapteur HTTP pour désactiver tout retry automatique
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=0))
sp._session = _session

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ─── PERSISTANCE ───────────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

tracked: dict = load_data()


# ─── HELPERS SPOTIFY (synchrones, exécutés dans un thread) ─────────────────────
def _get_latest_release(artist_id: str) -> dict | None:
    results = sp.artist_albums(
        artist_id,
        album_type="album,single,compilation",
        limit=5,
        country="FR"
    )
    items = results.get("items", [])
    if not items:
        return None
    items.sort(key=lambda x: x.get("release_date", "0000"), reverse=True)
    return items[0]

def _get_artist_from_url(url: str) -> dict | None:
    try:
        artist_id = url.split("/artist/")[1].split("?")[0].split("/")[0]
        return sp.artist(artist_id)
    except Exception:
        return None

async def get_latest_release(artist_id: str) -> dict | None:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_get_latest_release, artist_id))
    except SpotifyException as e:
        print(f"[get_latest_release] SpotifyException ({artist_id}) | HTTP {e.http_status} | msg: {e.msg} | reason: {e.reason}")
        raise
    except Exception as e:
        print(f"[get_latest_release] Erreur inattendue ({artist_id}) | {type(e).__name__}: {e}")
        raise

async def get_artist_from_url(url: str) -> dict | None:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_get_artist_from_url, url))
    except SpotifyException as e:
        print(f"[get_artist_from_url] SpotifyException (url={url}) | HTTP {e.http_status} | msg: {e.msg} | reason: {e.reason}")
        raise
    except Exception as e:
        print(f"[get_artist_from_url] Erreur inattendue (url={url}) | {type(e).__name__}: {e}")
        raise


# ─── VÉRIFICATION ──────────────────────────────────────────────────────────────
async def do_check(filter_name: str = None):
    channel = bot.get_channel(ANNOUNCE_CHANNEL)
    if not channel:
        return

    targets = {
        aid: info for aid, info in tracked.items()
        if filter_name is None or info["name"].lower() == filter_name.lower()
    }

    for artist_id, info in list(targets.items()):
        try:
            release = await get_latest_release(artist_id)
            if not release:
                continue

            if release["id"] != info.get("last_release_id"):
                tracked[artist_id]["last_release_id"] = release["id"]
                tracked[artist_id]["last_release_name"] = release["name"]
                tracked[artist_id]["last_release_url"]  = release["external_urls"]["spotify"]
                save_data(tracked)

                role    = channel.guild.get_role(NOTIFY_ROLE_ID)
                mention = role.mention if role else "@everyone"
                await channel.send(
                    f"{mention} Nouvelle sortie !\n"
                    f"[{info['name']} — {release['name']}]({release['external_urls']['spotify']})"
                )

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 3600)) if e.headers else 3600
                print(f"[do_check] Rate limit 429 sur '{info['name']}' — prochain essai dans ~{retry_after}s, cycle abandonné")
                return  # On abandonne ce cycle, la loop repassera dans 1h
            print(f"[do_check] SpotifyException sur '{info['name']}' ({artist_id}) | HTTP {e.http_status} | msg: {e.msg} | reason: {e.reason}")
        except Exception as e:
            print(f"[do_check] Erreur inattendue sur '{info['name']}' ({artist_id}) | {type(e).__name__}: {e}")

@tasks.loop(hours=1)
async def check_releases():
    await do_check()

@check_releases.before_loop
async def before_check():
    await bot.wait_until_ready()
    print("[check_releases] Attente de 10s avant le premier cycle...")
    await asyncio.sleep(10)


# ─── AUTOCOMPLETE ──────────────────────────────────────────────────────────────
async def artist_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=info["name"], value=info["name"])
        for info in tracked.values()
        if current.lower() in info["name"].lower()
    ][:25]


# ─── COMMANDES SLASH ───────────────────────────────────────────────────────────
@bot.tree.command(name="track", description="Suivre un artiste Spotify via son lien de page")
@app_commands.describe(url="Lien de la page Spotify de l'artiste (ex: https://open.spotify.com/artist/...)")
@app_commands.checks.has_permissions(manage_guild=True)
async def track(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)

    if "/artist/" not in url:
        await interaction.followup.send("❌ Lien invalide. Utilise bien un lien de page artiste Spotify.\nEx: `https://open.spotify.com/artist/...`", ephemeral=True)
        return

    try:
        artist = await get_artist_from_url(url)
        if not artist:
            await interaction.followup.send("❌ Impossible de récupérer l'artiste depuis ce lien.", ephemeral=True)
            return
    except SpotifyException as e:
        print(f"[/track] SpotifyException | HTTP {e.http_status} | msg: {e.msg} | reason: {e.reason}")
        await interaction.followup.send(f"❌ Erreur Spotify (HTTP {e.http_status}) : {e.msg}", ephemeral=True)
        return
    except Exception as e:
        print(f"[/track] Erreur inattendue | {type(e).__name__}: {e}")
        await interaction.followup.send("❌ Erreur inattendue, consulte les logs.", ephemeral=True)
        return

    aid  = artist["id"]
    name = artist["name"]

    if aid in tracked:
        await interaction.followup.send(f"⚠️ **{name}** est déjà suivi.", ephemeral=True)
        return

    try:
        release = await get_latest_release(aid)
    except Exception as e:
        print(f"[/track] Erreur récupération dernière sortie pour '{name}' | {type(e).__name__}: {e}")
        release = None

    tracked[aid] = {
        "name": name,
        "last_release_id": release["id"] if release else None
    }
    save_data(tracked)
    await interaction.followup.send(f"✅ **{name}** ajouté à la liste de suivi !", ephemeral=True)


@bot.tree.command(name="untrack", description="Arrêter de suivre un artiste")
@app_commands.describe(artiste="Nom de l'artiste à retirer")
@app_commands.autocomplete(artiste=artist_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def untrack(interaction: discord.Interaction, artiste: str):
    match = next((aid for aid, info in tracked.items()
                  if info["name"].lower() == artiste.lower()), None)
    if not match:
        await interaction.response.send_message(f"❌ **{artiste}** n'est pas dans la liste.", ephemeral=True)
        return

    name = tracked[match]["name"]
    del tracked[match]
    save_data(tracked)
    await interaction.response.send_message(f"🗑️ **{name}** retiré de la liste.", ephemeral=True)


@bot.tree.command(name="list", description="Voir les artistes suivis")
async def list_artists(interaction: discord.Interaction):
    if not tracked:
        await interaction.response.send_message("📭 Aucun artiste suivi pour l'instant.", ephemeral=True)
        return

    lines = [f"• **{info['name']}**" for info in tracked.values()]
    embed = discord.Embed(title="🎧 Artistes suivis", description="\n".join(lines), color=0x1DB954)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="latest", description="Afficher la dernière sortie connue d'un artiste suivi")
@app_commands.describe(artiste="Nom de l'artiste")
@app_commands.autocomplete(artiste=artist_autocomplete)
async def latest(interaction: discord.Interaction, artiste: str):
    match = next((
        (aid, info) for aid, info in tracked.items()
        if info["name"].lower() == artiste.lower()
    ), None)

    if not match:
        await interaction.response.send_message(
            f"❌ **{artiste}** n'est pas dans la liste de suivi. Utilise `/list` pour voir les artistes suivis.",
            ephemeral=True
        )
        return

    aid, info = match
    url  = info.get("last_release_url")
    name = info.get("last_release_name")

    if not url:
        await interaction.response.send_message(
            f"😕 Aucune sortie connue pour **{info['name']}** pour l'instant. Le bot n'a pas encore détecté de release.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"[{info['name']} — {name}]({url})"
    )


@bot.tree.command(name="check", description="Forcer une vérification immédiate (admin)")
@app_commands.describe(artiste="Artiste spécifique à vérifier, ou laisser vide pour tous")
@app_commands.autocomplete(artiste=artist_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.checks.cooldown(1, 60, key=lambda i: i.guild_id)  # 1 utilisation / 60s par serveur
async def force_check(interaction: discord.Interaction, artiste: str = None):
    await interaction.response.send_message(
        f"🔄 Vérification en cours{f' pour **{artiste}**' if artiste else ''}...", ephemeral=True
    )
    await do_check(filter_name=artiste)
    await interaction.followup.send("✅ Vérification terminée.", ephemeral=True)


# ─── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await bot.tree.sync()
    check_releases.start()
    print(f"✅ Bot connecté en tant que {bot.user} | {len(tracked)} artiste(s) suivis")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Tu n'as pas la permission.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)


# ─── LANCEMENT ─────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)