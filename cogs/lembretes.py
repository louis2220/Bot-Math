"""
Cog de Lembretes — sistema de lembretes sem banco de dados (em memória).
Os lembretes são perdidos se o bot reiniciar.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import time
import re
import logging
from datetime import timedelta

log = logging.getLogger('cogs.lembretes')

# Dicionário global: user_id -> lista de lembretes
# Cada lembrete: {'id': int, 'texto': str, 'tempo': float, 'canal': int, 'user': int}
_lembretes: dict[int, list[dict]] = {}
_proximo_id = 1


def parse_duracao(texto: str) -> int:
    """Converte uma string de duração em segundos.
    Ex: '10m', '2h', '1d 30m', '90s'
    Retorna None se inválido.
    """
    texto = texto.lower().strip()
    total = 0
    padroes = [
        (r'(\d+)\s*d(?:ia)?s?', 86400),
        (r'(\d+)\s*h(?:ora)?s?', 3600),
        (r'(\d+)\s*m(?:in(?:uto)?s?)?', 60),
        (r'(\d+)\s*s(?:eg(?:undo)?s?)?', 1),
    ]
    encontrou = False
    for padrao, mult in padroes:
        m = re.search(padrao, texto)
        if m:
            total += int(m.group(1)) * mult
            encontrou = True
    return total if encontrou else None


def formatar_duracao(segundos: int) -> str:
    """Formata segundos em string legível."""
    partes = []
    for nome, mult in [('dia', 86400), ('hora', 3600), ('min', 60), ('seg', 1)]:
        if segundos >= mult:
            val = segundos // mult
            segundos %= mult
            partes.append(f'{val} {nome}{"s" if val > 1 else ""}')
    return ', '.join(partes) if partes else '0 seg'


class Lembretes(commands.Cog, name='Lembretes'):
    """Sistema de lembretes (em memória — resets ao reiniciar o bot)."""

    def __init__(self, bot):
        self.bot = bot
        self.verificar_lembretes.start()

    def cog_unload(self):
        self.verificar_lembretes.cancel()

    @tasks.loop(seconds=15)
    async def verificar_lembretes(self):
        """Verifica e dispara lembretes vencidos."""
        global _proximo_id
        agora = time.time()
        para_remover = []

        for user_id, lista in _lembretes.items():
            vencidos = [l for l in lista if l['tempo'] <= agora]
            for lembrete in vencidos:
                try:
                    canal = self.bot.get_channel(lembrete['canal'])
                    user = self.bot.get_user(user_id)
                    if canal and user:
                        embed = discord.Embed(
                            title='⏰ Lembrete!',
                            description=lembrete['texto'],
                            color=0xFEE75C
                        )
                        embed.set_footer(text=f'Lembrete #{lembrete["id"]}')
                        await canal.send(f'{user.mention}', embed=embed)
                    elif user:
                        await user.send(f'⏰ Lembrete: {lembrete["texto"]}')
                except Exception as e:
                    log.warning(f'Erro ao disparar lembrete: {e}')
                para_remover.append((user_id, lembrete['id']))

        for user_id, lid in para_remover:
            if user_id in _lembretes:
                _lembretes[user_id] = [l for l in _lembretes[user_id] if l['id'] != lid]

    @verificar_lembretes.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @commands.command(name='lembrar', aliases=['lembrete', 'remind', 'remindme'])
    async def lembrar(self, ctx, duracao: str, *, texto: str):
        """Define um lembrete após um tempo especificado.

        Uso:
          .lembrar <duração> <mensagem>

        Duração: 10s, 5m, 2h, 1d, 1h30m, etc.

        Exemplos:
          .lembrar 10m Estudar trigonometria
          .lembrar 2h Fazer lista de integrais
          .lembrar 1d Revisão de álgebra linear
        """
        global _proximo_id
        segundos = parse_duracao(duracao)

        if segundos is None or segundos <= 0:
            return await ctx.send('❌ Duração inválida. Use: `10s`, `5m`, `2h`, `1d`, `1h30m`, etc.')
        if segundos > 86400 * 30:
            return await ctx.send('❌ Duração máxima: 30 dias.')
        if len(texto) > 500:
            return await ctx.send('❌ Mensagem muito longa (máx: 500 caracteres).')

        uid = ctx.author.id
        if uid not in _lembretes:
            _lembretes[uid] = []
        if len(_lembretes[uid]) >= 10:
            return await ctx.send('❌ Limite de 10 lembretes ativos. Use `.lembretes` para ver e `.lembrete_remover` para apagar.')

        lid = _proximo_id
        _proximo_id += 1

        _lembretes[uid].append({
            'id': lid,
            'texto': texto,
            'tempo': time.time() + segundos,
            'canal': ctx.channel.id,
            'user': uid,
        })

        embed = discord.Embed(title='⏰ Lembrete Definido!', color=0x2ECC71)
        embed.add_field(name='Mensagem', value=texto, inline=False)
        embed.add_field(name='Em', value=formatar_duracao(segundos), inline=True)
        embed.add_field(name='ID', value=f'`#{lid}`', inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='lembretes', aliases=['meus_lembretes', 'lista_lembretes'])
    async def listar_lembretes(self, ctx):
        """Lista seus lembretes ativos."""
        uid = ctx.author.id
        lista = _lembretes.get(uid, [])

        if not lista:
            return await ctx.send('📭 Você não tem lembretes ativos.')

        agora = time.time()
        embed = discord.Embed(title='📋 Seus Lembretes', color=0x5865F2)
        for l in lista:
            restante = max(0, int(l['tempo'] - agora))
            embed.add_field(
                name=f'#{l["id"]} — em {formatar_duracao(restante)}',
                value=l['texto'],
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name='lembrete_remover', aliases=['cancelar_lembrete', 'rm_lembrete'])
    async def remover_lembrete(self, ctx, id_lembrete: int):
        """Remove um lembrete pelo ID.

        Exemplos:
          .lembrete_remover 3
        """
        uid = ctx.author.id
        lista = _lembretes.get(uid, [])
        nova_lista = [l for l in lista if l['id'] != id_lembrete]

        if len(nova_lista) == len(lista):
            return await ctx.send(f'❌ Lembrete `#{id_lembrete}` não encontrado.')

        _lembretes[uid] = nova_lista
        await ctx.send(f'✅ Lembrete `#{id_lembrete}` removido.')


async def setup(bot):
    await bot.add_cog(Lembretes(bot))
