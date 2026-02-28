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
    PrevPageButton,
    NextPageButton,
    PageCounterButton,
    ConfirmYesButton,
    ConfirmNoButton,
    ConfirmAdminRemoveYes,
    ConfirmAdminRemoveNo,
    is_admin,
)


class ArtistListView(ui.LayoutView):
    """Vue principale avec pagination : follows / server / admin."""

    def __init__(self, user: discord.Member, guild: discord.Guild, page: str = "follows", page_index: int = 0):
        super().__init__(timeout=120)
        self.user = user
        self.page = page
        self.page_index = page_index
        self.message: discord.Message | None = None

        admin = is_admin(user, guild)

        # ── Construire le contenu de la page courante ──────────────────
        if page == "follows":
            items, total_pages = build_my_follows(user, guild, page_index)
        elif page == "server":
            items, total_pages = build_server_artists(user, guild, page_index)
        elif page == "admin" and admin:
            items, total_pages = build_admin_role_list(user, guild, page_index)
        else:
            items, total_pages = build_my_follows(user, guild, page_index)
            page = "follows"

        # Clamp page_index au cas où on serait hors bornes (ex: après suppression)
        self.page_index = max(0, min(page_index, total_pages - 1))

        # ── Container principal ────────────────────────────────────────
        container = ui.Container(*items, accent_color=0x1DB954)
        self.add_item(container)

        # ── Rangée de navigation : onglets + pagination ────────────────
        nav_follows = SwitchPageButton(target_page="follows", disabled=(page == "follows"))
        nav_server  = SwitchPageButton(target_page="server",  disabled=(page == "server"))

        prev_btn    = PrevPageButton(current_page_index=self.page_index, disabled=(self.page_index <= 0))
        counter_btn = PageCounterButton(current=self.page_index + 1, total=total_pages)
        next_btn    = NextPageButton(current_page_index=self.page_index, disabled=(self.page_index >= total_pages - 1))

        if admin:
            nav_admin = SwitchPageButton(target_page="admin", disabled=(page == "admin"))
            # Ligne 1 : onglets
            self.add_item(ui.ActionRow(nav_follows, nav_server, nav_admin))
        else:
            self.add_item(ui.ActionRow(nav_follows, nav_server))

        # Ligne 2 : flèches de pagination (masquée si une seule page)
        if total_pages > 1:
            self.add_item(ui.ActionRow(prev_btn, counter_btn, next_btn))

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
        parent_page_index: int = 0,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.guild = guild
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.parent_page = parent_page
        self.parent_page_index = parent_page_index
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
        parent_page_index: int = 0,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.guild = guild
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.parent_page_index = parent_page_index
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