import asyncio
from bot.config import DISCORD_TOKEN
from bot.discord.client import bot
from bot.utils.logger import log


async def main():
    async with bot:
        await bot.load_extension("bot.discord.commands")
        log.info("Démarrage du bot...")
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())