import discord
from discord import ui

from bot.ui.list_builder import (
    build_my_follows,
    build_server_artists,
    build_admin_role_list,
    build_confirm_unsub,
    build_confirm_admin_remove,
)
from bot.ui.list_buttons import (
    SwitchPageButton,
    ConfirmYesButton,
    ConfirmNoButton,
    ConfirmAdminRemoveYes,
    ConfirmAdminRemoveNo,
    is_admin,
)


class ArtistListView(ui.LayoutView):
    """Vue principale avec pagination : follows / server / admin."""

    def __init__(self, user: discord.Member, guild: discord.Guild, page: str = "follows"):
        super().__init__(timeout=120)
        self.user = user
        self.page = page
        self.message: discord.Message | None = None

        admin = is_admin(user, guild)

        # Construire le contenu
        if page == "follows":
            items = build_my_follows(user, guild)
        elif page == "server":
            items = build_server_artists(user, guild)
        elif page == "admin" and admin:
            items = build_admin_role_list(user, guild)
        else:
            items = build_my_follows(user, guild)
            page = "follows"

        # Container principal
        container = ui.Container(*items, accent_color=0x1DB954)
        self.add_item(container)

        # Boutons de navigation
        nav_buttons = []
        if page != "follows":
            nav_buttons.append(SwitchPageButton(target_page="follows"))
        if page != "server":
            nav_buttons.append(SwitchPageButton(target_page="server"))
        if admin and page != "admin":
            nav_buttons.append(SwitchPageButton(target_page="admin"))

        if nav_buttons:
            row = ui.ActionRow(*nav_buttons)
            self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.stop()


class ConfirmUnsubView(ui.LayoutView):
    """Confirmation de désabonnement utilisateur."""

    def __init__(
        self,
        user: discord.Member,
        guild: discord.Guild,
        artist_id: str,
        artist_name: str,
        parent_page: str,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.guild = guild
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.parent_page = parent_page
        self.message: discord.Message | None = None

        items = build_confirm_unsub(artist_name)
        container = ui.Container(*items, accent_color=0xFF0000)
        self.add_item(container)

        row = ui.ActionRow(ConfirmYesButton(), ConfirmNoButton())
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.stop()


class ConfirmAdminRemoveView(ui.LayoutView):
    """Confirmation de retrait du ping rôle (admin)."""

    def __init__(
        self,
        user: discord.Member,
        guild: discord.Guild,
        artist_id: str,
        artist_name: str,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.guild = guild
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.message: discord.Message | None = None

        items = build_confirm_admin_remove(artist_name)
        container = ui.Container(*items, accent_color=0xFF0000)
        self.add_item(container)

        row = ui.ActionRow(ConfirmAdminRemoveYes(), ConfirmAdminRemoveNo())
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.stop()