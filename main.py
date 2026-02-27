import asyncio
import logging
import os

import discord
from discord.ext import commands

from utils.db import Database
from utils.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=commands.when_mentioned_or(Config.PREFIX),
            intents=intents,
            help_command=None,
        )
        self.db: Database = None

    async def setup_hook(self):
        # Connect to database
        self.db = Database()
        await self.db.connect()
        await self.db.init_tables()

        # Load all cogs
        cogs = [
            "cogs.admin",
            "cogs.moderation",
            "cogs.tickets",
            "cogs.tags",
            "cogs.roles",
            "cogs.clopen",
            "cogs.modmail",
            "cogs.automod",
            "cogs.reminders",
            "cogs.logs",
            "cogs.help",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")

        # Sync slash commands
        await self.tree.sync()
        log.info("Slash commands synced.")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{Config.PREFIX}help",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Você não tem permissão para usar esse comando.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Argumento obrigatório faltando: `{error.param.name}`")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Argumento inválido: {error}")
            return
        log.error(f"Unhandled error in command {ctx.command}: {error}", exc_info=error)
        await ctx.send("❌ Ocorreu um erro inesperado.")


async def main():
    bot = Bot()
    async with bot:
        await bot.start(Config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
