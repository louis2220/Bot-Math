"""
Cog de Tags — sistema de factoids/tags persistidos em arquivo JSON.
Permite criar respostas rápidas para termos matemáticos.
"""

import discord
from discord.ext import commands
import json
import os
import logging
from pathlib import Path

log = logging.getLogger('cogs.tags')

TAGS_FILE = Path('data/tags.json')


def carregar_tags() -> dict:
    """Carrega tags do arquivo JSON."""
    if TAGS_FILE.exists():
        try:
            with open(TAGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f'Erro ao carregar tags: {e}')
    return {}


def salvar_tags(tags: dict):
    """Salva tags no arquivo JSON."""
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TAGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


class Tags(commands.Cog, name='Tags'):
    """Sistema de tags/factoids para respostas rápidas."""

    def __init__(self, bot):
        self.bot = bot
        self.tags = carregar_tags()

    @commands.group(name='tag', aliases=['t', 'tags'], invoke_without_command=True)
    async def tag(self, ctx, *, nome: str = None):
        """Exibe uma tag pelo nome, ou lista todas se nenhum nome for dado.

        Exemplos:
          .tag teorema pitagoras
          .tag derivada regra cadeia
          .tag (lista todas)
        """
        if nome is None:
            return await ctx.invoke(self.listar)

        nome_lower = nome.lower().strip()

        # Busca exata primeiro
        if nome_lower in self.tags:
            tag = self.tags[nome_lower]
            embed = discord.Embed(
                title=f'🏷️ {tag["nome"]}',
                description=tag['conteudo'],
                color=0x5865F2
            )
            embed.set_footer(text=f'Criado por {tag["criado_por"]} | Usos: {tag.get("usos", 0) + 1}')
            self.tags[nome_lower]['usos'] = tag.get('usos', 0) + 1
            salvar_tags(self.tags)
            return await ctx.send(embed=embed)

        # Busca parcial
        resultados = [k for k in self.tags if nome_lower in k]
        if resultados:
            lista = ', '.join([f'`{r}`' for r in resultados[:10]])
            return await ctx.send(f'🔍 Tag `{nome}` não encontrada. Tags similares: {lista}')

        await ctx.send(f'❌ Tag `{nome}` não encontrada. Use `.tag` para listar todas.')

    @tag.command(name='criar', aliases=['add', 'novo', 'new'])
    async def criar(self, ctx, nome: str, *, conteudo: str):
        """Cria uma nova tag.

        Uso:
          .tag criar <nome> <conteúdo>

        Exemplos:
          .tag criar pitagoras O teorema de Pitágoras diz que a² + b² = c²
          .tag criar "regra cadeia" d/dx[f(g(x))] = f'(g(x)) * g'(x)
        """
        nome_lower = nome.lower().strip()

        if len(nome_lower) > 50:
            return await ctx.send('❌ Nome muito longo (máx: 50 caracteres).')
        if len(conteudo) > 2000:
            return await ctx.send('❌ Conteúdo muito longo (máx: 2000 caracteres).')
        if nome_lower in self.tags:
            return await ctx.send(f'❌ Tag `{nome}` já existe. Use `.tag editar {nome}` para editar.')

        self.tags[nome_lower] = {
            'nome': nome,
            'conteudo': conteudo,
            'criado_por': str(ctx.author),
            'criado_por_id': ctx.author.id,
            'usos': 0,
        }
        salvar_tags(self.tags)
        await ctx.send(f'✅ Tag `{nome}` criada com sucesso!')

    @tag.command(name='editar', aliases=['edit', 'update'])
    async def editar(self, ctx, nome: str, *, novo_conteudo: str):
        """Edita o conteúdo de uma tag existente.
        Somente o criador ou um admin pode editar.

        Exemplos:
          .tag editar pitagoras Novo conteúdo aqui
        """
        nome_lower = nome.lower().strip()

        if nome_lower not in self.tags:
            return await ctx.send(f'❌ Tag `{nome}` não encontrada.')

        tag = self.tags[nome_lower]
        eh_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        eh_criador = tag.get('criado_por_id') == ctx.author.id

        if not (eh_admin or eh_criador):
            return await ctx.send('❌ Somente o criador da tag ou um administrador pode editá-la.')

        if len(novo_conteudo) > 2000:
            return await ctx.send('❌ Conteúdo muito longo (máx: 2000 caracteres).')

        self.tags[nome_lower]['conteudo'] = novo_conteudo
        salvar_tags(self.tags)
        await ctx.send(f'✅ Tag `{nome}` atualizada!')

    @tag.command(name='deletar', aliases=['delete', 'remover', 'rm'])
    async def deletar(self, ctx, *, nome: str):
        """Deleta uma tag. Somente o criador ou admin pode deletar.

        Exemplos:
          .tag deletar pitagoras
        """
        nome_lower = nome.lower().strip()

        if nome_lower not in self.tags:
            return await ctx.send(f'❌ Tag `{nome}` não encontrada.')

        tag = self.tags[nome_lower]
        eh_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        eh_criador = tag.get('criado_por_id') == ctx.author.id

        if not (eh_admin or eh_criador):
            return await ctx.send('❌ Somente o criador da tag ou um administrador pode deletá-la.')

        del self.tags[nome_lower]
        salvar_tags(self.tags)
        await ctx.send(f'✅ Tag `{nome}` removida.')

    @tag.command(name='lista', aliases=['list', 'listar', 'all', 'todas'])
    async def listar(self, ctx):
        """Lista todas as tags disponíveis."""
        if not self.tags:
            return await ctx.send('📭 Nenhuma tag cadastrada ainda. Use `.tag criar <nome> <conteúdo>` para criar uma.')

        embed = discord.Embed(title='🏷️ Tags Disponíveis', color=0x5865F2)
        embed.description = f'Total: **{len(self.tags)}** tags\nUse `.tag <nome>` para exibir.\n'

        # Agrupar em blocos para evitar limite
        nomes = sorted(self.tags.keys())
        blocos = [nomes[i:i+20] for i in range(0, len(nomes), 20)]
        for i, bloco in enumerate(blocos[:5]):
            embed.add_field(
                name=f'Tags {i*20+1}–{i*20+len(bloco)}',
                value=', '.join([f'`{n}`' for n in bloco]),
                inline=False
            )
        if len(blocos) > 5:
            embed.set_footer(text=f'Mostrando 100 de {len(self.tags)} tags.')
        await ctx.send(embed=embed)

    @tag.command(name='info')
    async def info_tag(self, ctx, *, nome: str):
        """Exibe informações sobre uma tag.

        Exemplos:
          .tag info pitagoras
        """
        nome_lower = nome.lower().strip()
        if nome_lower not in self.tags:
            return await ctx.send(f'❌ Tag `{nome}` não encontrada.')

        tag = self.tags[nome_lower]
        embed = discord.Embed(title=f'ℹ️ Info: {tag["nome"]}', color=0x3498DB)
        embed.add_field(name='Criado por', value=tag.get('criado_por', 'Desconhecido'), inline=True)
        embed.add_field(name='Usos', value=str(tag.get('usos', 0)), inline=True)
        embed.add_field(name='Conteúdo (prévia)', value=tag['conteudo'][:100] + ('...' if len(tag['conteudo']) > 100 else ''), inline=False)
        await ctx.send(embed=embed)

    @tag.command(name='top', aliases=['popular', 'ranking'])
    async def top_tags(self, ctx):
        """Exibe as tags mais usadas."""
        if not self.tags:
            return await ctx.send('📭 Nenhuma tag cadastrada.')

        ordenadas = sorted(self.tags.items(), key=lambda x: x[1].get('usos', 0), reverse=True)[:10]
        embed = discord.Embed(title='🏆 Tags Mais Usadas', color=0xF1C40F)
        for i, (nome, tag) in enumerate(ordenadas, 1):
            embed.add_field(
                name=f'{i}. {tag["nome"]}',
                value=f'{tag.get("usos", 0)} uso(s)',
                inline=True
            )
        await ctx.send(embed=embed)

    @tag.command(name='buscar', aliases=['search', 'procurar'])
    async def buscar_tag(self, ctx, *, termo: str):
        """Busca tags pelo nome ou conteúdo.

        Exemplos:
          .tag buscar derivada
          .tag buscar integral
        """
        termo_lower = termo.lower()
        resultados = {
            k: v for k, v in self.tags.items()
            if termo_lower in k or termo_lower in v['conteudo'].lower()
        }

        if not resultados:
            return await ctx.send(f'🔍 Nenhuma tag encontrada para `{termo}`.')

        embed = discord.Embed(title=f'🔍 Busca: "{termo}"', color=0x9B59B6)
        embed.description = f'{len(resultados)} resultado(s):'
        for nome, tag in list(resultados.items())[:10]:
            embed.add_field(name=tag['nome'], value=tag['conteudo'][:80] + '...', inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Tags(bot))
