import discord
from discord import app_commands
from discord.ext import commands
from spotipy.exceptions import SpotifyException

from bot.config import ADMIN_ROLE_ID
from bot.data.storage import tracked, save_data, add_artist, cleanup_artist
from bot.spotify.api import get_artist_from_url, get_latest_release
from bot.spotify.checker import do_check
from bot.utils.autocomplete import artist_autocomplete
from bot.utils.logger import log


def has_admin_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        role = interaction.guild.get_role(ADMIN_ROLE_ID)
        if not role:
            log.warning(f"Rôle admin introuvable (ID={ADMIN_ROLE_ID})")
            return False
        return role in interaction.user.roles
    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /admin-follow ──────────────────────────────────────────────────
    @app_commands.command(name="admin-follow", description="[Admin] Ajouter un artiste avec notification rôle")
    @app_commands.describe(url="Lien de la page Spotify de l'artiste")
    @has_admin_role()
    async def admin_follow(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)

        if "/artist/" not in url:
            await interaction.followup.send(
                "❌ Lien invalide. Utilise un lien artiste Spotify.\n"
                "Ex: `https://open.spotify.com/artist/...`",
                ephemeral=True
            )
            return

        try:
            artist = await get_artist_from_url(url)
            if not artist:
                await interaction.followup.send("❌ Impossible de récupérer l'artiste.", ephemeral=True)
                return
        except SpotifyException as e:
            log.error(f"/admin-follow SpotifyException | HTTP {e.http_status} | {e.msg}")
            await interaction.followup.send(f"❌ Erreur Spotify (HTTP {e.http_status}) : {e.msg}", ephemeral=True)
            return
        except Exception as e:
            log.error(f"/admin-follow Erreur inattendue | {type(e).__name__}: {e}")
            await interaction.followup.send("❌ Une erreur inattendue est survenue.", ephemeral=True)
            return

        gid  = interaction.guild_id
        aid  = artist["id"]
        name = artist["name"]

        guild_data = tracked.get(str(gid), {})
        if aid in guild_data and guild_data[aid].get("notify_role"):
            await interaction.followup.send(f"⚠️ **{name}** a déjà le ping rôle activé.", ephemeral=True)
            return

        try:
            release = await get_latest_release(aid)
        except Exception as e:
            log.warning(f"/admin-follow Impossible de récupérer la dernière sortie de '{name}' | {e}")
            release = None

        created = add_artist(gid, artist, release, notify_role=True, user_id=None)
        action  = "ajouté avec" if created else "ping rôle activé —"
        log.info(f"[Guild {gid}] {action} notification rôle : {name} ({aid})")
        await interaction.followup.send(f"✅ **{name}** — {action} notification rôle !", ephemeral=True)

    # ── /admin-unfollow ────────────────────────────────────────────────
    @app_commands.command(name="admin-unfollow", description="[Admin] Retirer un artiste ou désactiver le ping rôle")
    @app_commands.describe(
        artiste="Nom de l'artiste",
        force="Supprimer complètement l'artiste (même s'il a des abonnés)"
    )
    @app_commands.autocomplete(artiste=artist_autocomplete)
    @has_admin_role()
    async def admin_unfollow(self, interaction: discord.Interaction, artiste: str, force: bool = False):
        gid        = interaction.guild_id
        guild_data = tracked.get(str(gid), {})

        match = next((aid for aid, info in guild_data.items()
                      if info["name"].lower() == artiste.lower()), None)
        if not match:
            await interaction.response.send_message(f"❌ **{artiste}** n'est pas dans la liste.", ephemeral=True)
            return

        info = guild_data[match]
        name = info["name"]

        if force:
            sub_count = len(info.get("subscribers", []))
            del tracked[str(gid)][match]
            if not tracked[str(gid)]:
                del tracked[str(gid)]
            save_data(tracked)
            log.info(f"[Guild {gid}] Artiste supprimé (force) : {name} — {sub_count} abonné(s) retirés")
            await interaction.response.send_message(
                f"🗑️ **{name}** supprimé ({sub_count} abonné(s) retirés).", ephemeral=True
            )
            return

        if not info.get("notify_role"):
            await interaction.response.send_message(
                f"⚠️ **{name}** n'a pas le ping rôle activé. Utilise `force:True` pour supprimer.",
                ephemeral=True
            )
            return

        info["notify_role"] = False
        save_data(tracked)
        log.info(f"[Guild {gid}] Ping rôle désactivé pour : {name}")
        cleanup_artist(gid, match)

        await interaction.response.send_message(
            f"✅ Ping rôle désactivé pour **{name}**.", ephemeral=True
        )

    # ── /admin-check ───────────────────────────────────────────────────
    @app_commands.command(name="admin-check", description="[Admin] Forcer une vérification immédiate")
    @app_commands.describe(artiste="Artiste spécifique à vérifier, ou laisser vide pour tous")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    @has_admin_role()
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.guild_id)
    async def admin_check(self, interaction: discord.Interaction, artiste: str = None):
        await interaction.response.send_message(
            f"🔄 Vérification en cours{f' pour **{artiste}**' if artiste else ''}...",
            ephemeral=True
        )
        await do_check(interaction.client, filter_name=artiste, guild_id=interaction.guild_id)
        await interaction.followup.send("✅ Vérification terminée.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    log.info("Cog AdminCog chargé")