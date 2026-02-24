import discord
from discord import ui

from bot.config import ADMIN_ROLE_ID
from bot.data.storage import tracked, save_data, cleanup_artist
from bot.utils.logger import log


# ── Boutons utilisateur ────────────────────────────────────────────────


class SubscribeButton(ui.Button):
    """Bouton 🔔 pour s'abonner à un artiste."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="🔔",
            style=discord.ButtonStyle.success,
            custom_id=f"sub:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        uid = interaction.user.id
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(self.artist_id)

        if not info:
            await interaction.response.send_message(
                f"❌ **{self.artist_name}** n'existe plus dans la liste.", ephemeral=True
            )
            return

        subs = info.setdefault("subscribers", [])
        if uid in subs:
            await interaction.response.send_message(
                f"⚠️ Tu es déjà abonné(e) à **{self.artist_name}**.", ephemeral=True
            )
            return

        subs.append(uid)
        save_data(tracked)
        log.info(f"[Guild {gid}] Abonné ajouté via UI : {interaction.user} → {self.artist_name}")

        from bot.ui.list_view import ArtistListView
        view = ArtistListView(interaction.user, interaction.guild, page=self.view.page)
        await interaction.response.edit_message(view=view)


class UnsubscribeButton(ui.Button):
    """Bouton ❌ pour se désabonner (ouvre la confirmation)."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id=f"unsub:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ConfirmUnsubView
        view = ConfirmUnsubView(
            user=interaction.user,
            guild=interaction.guild,
            artist_id=self.artist_id,
            artist_name=self.artist_name,
            parent_page=self.view.page,
        )
        await interaction.response.edit_message(view=view)


class ConfirmYesButton(ui.Button):
    """Confirme le désabonnement."""

    def __init__(self):
        super().__init__(label="Confirmer", emoji="✅", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: "ConfirmUnsubView" = self.view
        uid = interaction.user.id
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(view.artist_id)

        if info:
            subs = info.get("subscribers", [])
            if uid in subs:
                subs.remove(uid)
                save_data(tracked)
                log.info(f"[Guild {gid}] Abonné retiré via UI : {interaction.user} → {view.artist_name}")
                cleanup_artist(int(gid), view.artist_id)

        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page=view.parent_page)
        await interaction.response.edit_message(view=new_view)


class ConfirmNoButton(ui.Button):
    """Annule le désabonnement."""

    def __init__(self):
        super().__init__(label="Annuler", emoji="↩️", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "ConfirmUnsubView" = self.view
        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page=view.parent_page)
        await interaction.response.edit_message(view=new_view)


# ── Bouton navigation ─────────────────────────────────────────────────


class SwitchPageButton(ui.Button):
    """Bouton pour changer de page."""

    def __init__(self, target_page: str):
        labels = {
            "server":  ("📋", "Artistes du serveur"),
            "follows": ("🔔", "Mes follows"),
            "admin":   ("⚙️", "Liste rôle"),
        }
        emoji, label = labels.get(target_page, ("❓", target_page))
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
        self.target_page = target_page

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ArtistListView
        view = ArtistListView(interaction.user, interaction.guild, page=self.target_page)
        await interaction.response.edit_message(view=view)


# ── Boutons admin ──────────────────────────────────────────────────────


class AdminAddRoleButton(ui.Button):
    """Bouton ⚙️ pour ajouter un artiste à la liste du rôle générique."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="📌",
            style=discord.ButtonStyle.primary,
            custom_id=f"admin_add:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(self.artist_id)

        if not info:
            await interaction.response.send_message(
                f"❌ **{self.artist_name}** n'existe plus.", ephemeral=True
            )
            return

        if info.get("notify_role"):
            await interaction.response.send_message(
                f"⚠️ **{self.artist_name}** a déjà le ping rôle.", ephemeral=True
            )
            return

        info["notify_role"] = True
        save_data(tracked)
        log.info(f"[Guild {gid}] Ping rôle activé via UI : {self.artist_name}")

        from bot.ui.list_view import ArtistListView
        view = ArtistListView(interaction.user, interaction.guild, page=self.view.page)
        await interaction.response.edit_message(view=view)


class AdminRemoveRoleButton(ui.Button):
    """Bouton pour retirer un artiste de la liste du rôle générique."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id=f"admin_rm:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ConfirmAdminRemoveView
        view = ConfirmAdminRemoveView(
            user=interaction.user,
            guild=interaction.guild,
            artist_id=self.artist_id,
            artist_name=self.artist_name,
        )
        await interaction.response.edit_message(view=view)


class ConfirmAdminRemoveYes(ui.Button):
    """Confirme le retrait du ping rôle."""

    def __init__(self):
        super().__init__(label="Confirmer", emoji="✅", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: "ConfirmAdminRemoveView" = self.view
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(view.artist_id)

        if info:
            info["notify_role"] = False
            save_data(tracked)
            log.info(f"[Guild {gid}] Ping rôle désactivé via UI : {view.artist_name}")
            cleanup_artist(int(gid), view.artist_id)

        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page="admin")
        await interaction.response.edit_message(view=new_view)


class ConfirmAdminRemoveNo(ui.Button):
    """Annule le retrait du ping rôle."""

    def __init__(self):
        super().__init__(label="Annuler", emoji="↩️", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page="admin")
        await interaction.response.edit_message(view=new_view)


# ── Helpers ────────────────────────────────────────────────────────────


def is_admin(user: discord.Member, guild: discord.Guild) -> bool:
    """Vérifie si l'utilisateur a le rôle admin."""
    role = guild.get_role(ADMIN_ROLE_ID)
    if not role:
        return False
    return role in user.roles