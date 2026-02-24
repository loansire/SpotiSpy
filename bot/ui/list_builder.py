import discord
from discord import ui

from bot.data.storage import tracked
from bot.ui.list_buttons import (
    SubscribeButton,
    UnsubscribeButton,
    AdminAddRoleButton,
    AdminRemoveRoleButton,
    is_admin,
)


def _artist_text(info: dict) -> str:
    """Texte formaté pour un artiste."""
    text = f"**{info['name']}**"
    last = info.get("last_release_name")
    if last:
        text += f"\n-# Dernière sortie : {last}"
    return text


def build_my_follows(user: discord.Member, guild: discord.Guild) -> list:
    """Page 'Mes follows' — artistes auxquels l'utilisateur est abonné."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})
    admin = is_admin(user, guild)

    components = []
    components.append(ui.TextDisplay("## 🔔 Mes follows"))
    components.append(ui.Separator(visible=True))

    followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid in info.get("subscribers", [])
    ]

    if not followed:
        components.append(ui.TextDisplay("*Tu ne suis aucun artiste pour le moment.*"))
        return components

    for aid, info in followed:
        img = info.get("image_url")
        if img:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
                accessory=ui.Thumbnail(img),
            )
        else:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
            )
        components.append(section)
        buttons = [UnsubscribeButton(artist_id=aid, artist_name=info["name"])]
        if admin and not info.get("notify_role"):
            buttons.append(AdminAddRoleButton(artist_id=aid, artist_name=info["name"]))
        components.append(ui.ActionRow(*buttons))

    return components


def build_server_artists(user: discord.Member, guild: discord.Guild) -> list:
    """Page 'Artistes du serveur' — artistes non suivis par l'utilisateur."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})
    admin = is_admin(user, guild)

    components = []
    components.append(ui.TextDisplay("## 📋 Artistes du serveur"))
    components.append(ui.Separator(visible=True))

    not_followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid not in info.get("subscribers", [])
    ]

    if not not_followed:
        components.append(ui.TextDisplay("*Tu suis déjà tous les artistes du serveur !*"))
        return components

    for aid, info in not_followed:
        img = info.get("image_url")
        if img:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
                accessory=ui.Thumbnail(img),
            )
        else:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
            )
        components.append(section)
        buttons = [SubscribeButton(artist_id=aid, artist_name=info["name"])]
        if admin and not info.get("notify_role"):
            buttons.append(AdminAddRoleButton(artist_id=aid, artist_name=info["name"]))
        components.append(ui.ActionRow(*buttons))

    return components


def build_admin_role_list(user: discord.Member, guild: discord.Guild) -> list:
    """Page admin — artistes avec notify_role activé."""
    gid = str(guild.id)
    guild_data = tracked.get(gid, {})

    components = []
    components.append(ui.TextDisplay("## ⚙️ Liste du rôle générique"))
    components.append(ui.Separator(visible=True))

    role_artists = [
        (aid, info) for aid, info in guild_data.items()
        if info.get("notify_role")
    ]

    if not role_artists:
        components.append(ui.TextDisplay("*Aucun artiste n'a le ping rôle activé.*"))
        return components

    for aid, info in role_artists:
        img = info.get("image_url")
        if img:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
                accessory=ui.Thumbnail(img),
            )
        else:
            section = ui.Section(
                ui.TextDisplay(_artist_text(info)),
            )
        components.append(section)
        components.append(ui.ActionRow(AdminRemoveRoleButton(artist_id=aid, artist_name=info["name"])))

    return components


def build_confirm_unsub(artist_name: str) -> list:
    """Confirmation de désabonnement."""
    return [
        ui.TextDisplay("## ⚠️ Confirmation"),
        ui.Separator(visible=True),
        ui.TextDisplay(f"Te désabonner de **{artist_name}** ?"),
    ]


def build_confirm_admin_remove(artist_name: str) -> list:
    """Confirmation de retrait du ping rôle."""
    return [
        ui.TextDisplay("## ⚠️ Confirmation"),
        ui.Separator(visible=True),
        ui.TextDisplay(f"Retirer **{artist_name}** de la liste du rôle ?"),
    ]