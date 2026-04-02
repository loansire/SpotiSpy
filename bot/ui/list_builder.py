import discord
from discord import ui

from bot.data import storage
from bot.ui.list_buttons import (
    SubscribeButton,
    UnsubscribeButton,
)

PAGE_SIZE = 4  # Artistes affichés par page


def _artist_text(artist: dict) -> str:
    """Texte formaté pour un artiste."""
    text = f"**{artist['name']}**"
    last = artist.get("last_release_name")
    if last:
        text += f"\n-# Dernière sortie : {last}"
    return text


def _paginate(items: list, page_index: int) -> tuple[list, int]:
    """Retourne (slice de la page, nombre total de pages)."""
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_index = max(0, min(page_index, total_pages - 1))
    start = page_index * PAGE_SIZE
    return items[start:start + PAGE_SIZE], total_pages


async def build_my_follows(user: discord.Member, guild: discord.Guild, page_index: int = 0) -> tuple[list, int]:
    """Page 'Mes follows' — artistes auxquels l'utilisateur est abonné."""
    uid = user.id
    all_artists = await storage.get_guild_artists(guild.id)

    followed = []
    for artist in all_artists:
        if await storage.is_subscribed(guild.id, artist["artist_id"], uid):
            followed.append(artist)

    page_items, total_pages = _paginate(followed, page_index)

    components = []
    components.append(ui.TextDisplay("## 🔔 Mes follows"))
    components.append(ui.Separator(visible=True))

    if not followed:
        components.append(ui.TextDisplay("*Tu ne suis aucun artiste pour le moment.*"))
        return components, 1

    for i, artist in enumerate(page_items):
        if i > 0:
            components.append(ui.Separator(visible=True))
        img = artist.get("image_url")
        text = ui.TextDisplay(_artist_text(artist))
        if img:
            components.append(ui.Section(text, accessory=ui.Thumbnail(img)))
        else:
            components.append(text)
        components.append(ui.ActionRow(UnsubscribeButton(artist_id=artist["artist_id"], artist_name=artist["name"])))

    return components, total_pages


async def build_server_artists(user: discord.Member, guild: discord.Guild, page_index: int = 0) -> tuple[list, int]:
    """Page 'Artistes du serveur' — artistes non suivis par l'utilisateur."""
    uid = user.id
    all_artists = await storage.get_guild_artists(guild.id)

    not_followed = []
    for artist in all_artists:
        if not await storage.is_subscribed(guild.id, artist["artist_id"], uid):
            not_followed.append(artist)

    page_items, total_pages = _paginate(not_followed, page_index)

    components = []
    components.append(ui.TextDisplay("## 📋 Artistes du serveur"))
    components.append(ui.Separator(visible=True))

    if not not_followed:
        components.append(ui.TextDisplay("*Tu suis déjà tous les artistes du serveur !*"))
        return components, 1

    for i, artist in enumerate(page_items):
        if i > 0:
            components.append(ui.Separator(visible=True))
        img = artist.get("image_url")
        text = ui.TextDisplay(_artist_text(artist))
        if img:
            components.append(ui.Section(text, accessory=ui.Thumbnail(img)))
        else:
            components.append(text)
        components.append(ui.ActionRow(SubscribeButton(artist_id=artist["artist_id"], artist_name=artist["name"])))

    return components, total_pages


def build_confirm_unsub(artist_name: str) -> list:
    """Confirmation de désabonnement (pas de DB, reste synchrone)."""
    return [
        ui.TextDisplay("## ⚠️ Confirmation"),
        ui.Separator(visible=True),
        ui.TextDisplay(f"Te désabonner de **{artist_name}** ?"),
    ]