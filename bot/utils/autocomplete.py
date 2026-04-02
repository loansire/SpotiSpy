import discord
from discord import app_commands
from bot.data import storage


async def artist_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete tous les artistes du serveur."""
    artists = await storage.get_guild_artists(interaction.guild_id)
    return [
        app_commands.Choice(name=a["name"], value=a["name"])
        for a in artists
        if current.lower() in a["name"].lower()
    ][:25]


async def subscribed_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete uniquement les artistes auxquels l'utilisateur est abonné."""
    artists = await storage.get_guild_artists(interaction.guild_id)
    uid = interaction.user.id
    results = []
    for a in artists:
        if current.lower() in a["name"].lower():
            if await storage.is_subscribed(interaction.guild_id, a["artist_id"], uid):
                results.append(app_commands.Choice(name=a["name"], value=a["name"]))
        if len(results) >= 25:
            break
    return results