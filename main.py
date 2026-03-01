"""
Bot de Matemática para Discord
Desenvolvido para servidores brasileiros de matemática.
"""

import discord
from discord.ext import commands
import os
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('bot')

# Prefixo padrão
PREFIX = os.environ.get('BOT_PREFIX', '.')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Lista de cogs para carregar
COGS = [
    'cogs.matematica',
    'cogs.utilidades',
    'cogs.lembretes',
    'cogs.tags',
    'cogs.roles_review',
]


@bot.event
async def on_ready():
    log.info(f'Bot conectado como {bot.user} (ID: {bot.user.id})')
    log.info(f'Prefixo: {PREFIX}')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f'{PREFIX}ajuda | Matemática'
        )
    )


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'❌ Argumento faltando: `{error.param.name}`. Use `{PREFIX}ajuda {ctx.command}` para ver como usar.')
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f'❌ Argumento inválido. Use `{PREFIX}ajuda {ctx.command}` para ver como usar.')
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'⏳ Aguarde {error.retry_after:.1f}s antes de usar este comando novamente.')
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ Você não tem permissão para usar este comando.')
    else:
        log.error(f'Erro no comando {ctx.command}: {error}', exc_info=error)
        await ctx.send(f'❌ Ocorreu um erro inesperado: `{error}`')


async def main():
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                log.info(f'Cog carregado: {cog}')
            except Exception as e:
                log.error(f'Falha ao carregar cog {cog}: {e}', exc_info=e)

        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            log.critical('DISCORD_TOKEN não encontrado nas variáveis de ambiente!')
            return
        await bot.start(token)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
