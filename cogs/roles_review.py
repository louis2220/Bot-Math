"""
Cog de Seleção de Cargos com Revisão.

Níveis:
  - Pré-Universitário → cargo dado imediatamente
  - Graduação         → cargo dado imediatamente
  - Mestrado          → abre formulário → cargo "Pendente" → revisão do staff
  - Doutorado         → abre formulário → cargo "Pendente" → revisão do staff

Configuração:
  Use .config_cargos para configurar. Para reconfigurar, rode novamente.
"""

import discord
from discord.ext import commands
import json
import os
import logging
from pathlib import Path

log = logging.getLogger('cogs.roles_review')

CONFIG_FILE = Path('data/roles_config.json')


def _cfg_default() -> dict:
    return {
        "cargo_pre":      int(os.environ.get("CARGO_PRE_UNIVERSITARIO", 0)),
        "cargo_grad":     int(os.environ.get("CARGO_GRADUACAO", 0)),
        "cargo_mestrado": int(os.environ.get("CARGO_MESTRADO", 0)),
        "cargo_dout":     int(os.environ.get("CARGO_DOUTORADO", 0)),
        "cargo_pendente": int(os.environ.get("CARGO_PENDENTE", 0)),
        "canal_revisao":  int(os.environ.get("CANAL_REVISAO", 0)),
    }


def carregar_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                data = json.load(f)
                cfg = _cfg_default()
                cfg.update(data)
                return cfg
        except Exception:
            pass
    return _cfg_default()


def salvar_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ─── Modal: formulário de Mestrado/Doutorado ─────────────────────────────────
# Labels: máximo 45 caracteres (limite do Discord)

class FormularioAvancado(discord.ui.Modal):

    qual_matematica = discord.ui.TextInput(
        label='Qual área da matemática te interessa?',
        placeholder='Ex: Topologia, Álgebra, Análise Real...',
        style=discord.TextStyle.paragraph,
        max_length=600,
        required=True,
    )
    background = discord.ui.TextInput(
        label='Qual é sua formação/background?',
        placeholder='Responda só se quiser. Ex: cursando mestrado em...',
        style=discord.TextStyle.paragraph,
        max_length=600,
        required=False,
    )
    papers_livros = discord.ui.TextInput(
        label='Quais papers/livros leu recentemente?',
        placeholder='Nos conte o que achou interessante!',
        style=discord.TextStyle.paragraph,
        max_length=600,
        required=True,
    )

    def __init__(self, cog: 'RolesReview', nivel: str):
        # nivel = 'Mestrado' ou 'Doutorado'
        super().__init__(title=f'Solicitação — {nivel}')
        self.cog = cog
        self.nivel = nivel

    async def on_submit(self, interaction: discord.Interaction):
        cfg = self.cog.cfg
        guild = interaction.guild
        member = interaction.user

        cargo_pendente = guild.get_role(cfg['cargo_pendente'])
        cargos_nivel = [
            guild.get_role(cfg['cargo_pre']),
            guild.get_role(cfg['cargo_grad']),
            guild.get_role(cfg['cargo_mestrado']),
            guild.get_role(cfg['cargo_dout']),
        ]

        try:
            para_remover = [r for r in cargos_nivel if r and r in member.roles]
            if para_remover:
                await member.remove_roles(*para_remover, reason='Troca de nível')
            if cargo_pendente:
                await member.add_roles(cargo_pendente, reason=f'Aguardando revisão — {self.nivel}')
        except discord.Forbidden:
            await interaction.response.send_message(
                '❌ Não tenho permissão para gerenciar cargos. Contate um administrador.',
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f'✅ **Formulário de {self.nivel} enviado!** Você recebeu o cargo **Pendente** '
            f'enquanto a equipe avalia. Você será notificado quando houver uma decisão.',
            ephemeral=True
        )

        canal = guild.get_channel(cfg['canal_revisao'])
        if not canal:
            log.warning(f'Canal de revisão não encontrado (ID: {cfg["canal_revisao"]})')
            return

        emoji = '📙' if self.nivel == 'Mestrado' else '📕'
        embed = discord.Embed(
            title=f'{emoji} Nova Solicitação — {self.nivel}',
            color=0x9B59B6 if self.nivel == 'Mestrado' else 0xE74C3C,
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name='Usuário', value=f'{member.mention} (`{member.id}`)', inline=False)
        embed.add_field(name='Nível solicitado', value=f'**{self.nivel}**', inline=False)
        embed.add_field(name='🔬 Área de interesse', value=self.qual_matematica.value or '*(não respondido)*', inline=False)
        embed.add_field(name='🎓 Formação/background', value=self.background.value or '*(não respondido)*', inline=False)
        embed.add_field(name='📚 Papers/livros recentes', value=self.papers_livros.value or '*(não respondido)*', inline=False)
        embed.set_footer(text=f'ID: {member.id}')

        # Passa o nível para os botões saberem qual cargo dar se aprovado
        view = BotoesRevisao(self.cog, member.id, self.nivel)
        await canal.send(embed=embed, view=view)


# ─── View: botões de revisão para staff ──────────────────────────────────────

class BotoesRevisao(discord.ui.View):
    def __init__(self, cog: 'RolesReview', user_id: int, nivel: str = 'Mestrado'):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.nivel = nivel  # 'Mestrado' ou 'Doutorado'

    @discord.ui.button(label='✅ Aprovar', style=discord.ButtonStyle.success, custom_id='revisao:aprovar')
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._processar(interaction, aprovado=True)

    @discord.ui.button(label='❌ Rejeitar', style=discord.ButtonStyle.danger, custom_id='revisao:rejeitar')
    async def rejeitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._processar(interaction, aprovado=False)

    async def _processar(self, interaction: discord.Interaction, aprovado: bool):
        cfg = self.cog.cfg
        guild = interaction.guild

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                '❌ Você não tem permissão para revisar solicitações.', ephemeral=True)
            return

        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message(
                '❌ Usuário não encontrado (pode ter saído do servidor).', ephemeral=True)
            self._desabilitar_botoes()
            await interaction.message.edit(view=self)
            return

        cargo_pendente = guild.get_role(cfg['cargo_pendente'])
        # Cargo a dar: Mestrado ou Doutorado dependendo do que foi solicitado
        cargo_aprovado = guild.get_role(
            cfg['cargo_mestrado'] if self.nivel == 'Mestrado' else cfg['cargo_dout']
        )

        try:
            if cargo_pendente and cargo_pendente in member.roles:
                await member.remove_roles(cargo_pendente, reason=f'Revisão por {interaction.user}')
            if aprovado and cargo_aprovado:
                await member.add_roles(cargo_aprovado, reason=f'Aprovado por {interaction.user}')
            try:
                if aprovado:
                    await member.send(
                        f'🎉 **Parabéns!** Sua solicitação de **{self.nivel}** foi **aprovada** '
                        f'por {interaction.user} no servidor **{guild.name}**!'
                    )
                else:
                    await member.send(
                        f'❌ Sua solicitação de **{self.nivel}** no servidor **{guild.name}** '
                        f'foi **rejeitada** por {interaction.user}. '
                        f'Pode tentar novamente ou entrar em contato com a equipe.'
                    )
            except discord.Forbidden:
                pass
        except discord.Forbidden:
            await interaction.response.send_message(
                '❌ Não tenho permissão para gerenciar cargos.', ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        status = '✅ APROVADO' if aprovado else '❌ REJEITADO'
        embed.color = 0x2ECC71 if aprovado else 0xED4245
        embed.set_footer(text=f'{status} por {interaction.user} | ID: {self.user_id}')
        self._desabilitar_botoes()
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f'{"✅ Aprovado" if aprovado else "❌ Rejeitado"}: {member.mention}', ephemeral=True)

    def _desabilitar_botoes(self):
        for item in self.children:
            item.disabled = True


# ─── View: dropdown de seleção de nível ──────────────────────────────────────

class SeletorNivel(discord.ui.View):
    def __init__(self, cog: 'RolesReview'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder='Selecione seu nível de matemática...',
        custom_id='nivel:select',
        options=[
            discord.SelectOption(
                label='Pré-Universitário',
                description='Ensino médio, vestibulandos, olimpíadas.',
                emoji='📘',
                value='pre',
            ),
            discord.SelectOption(
                label='Graduação',
                description='Cursando ou graduado em curso superior.',
                emoji='📗',
                value='grad',
            ),
            discord.SelectOption(
                label='Mestrado',
                description='Cursando ou concluído mestrado. Requer revisão.',
                emoji='📙',
                value='mestrado',
            ),
            discord.SelectOption(
                label='Doutorado',
                description='Cursando ou concluído doutorado. Requer revisão.',
                emoji='📕',
                value='doutorado',
            ),
        ]
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        escolha = select.values[0]
        cfg = self.cog.cfg
        guild = interaction.guild
        member = interaction.user

        cargo_pre      = guild.get_role(cfg['cargo_pre'])
        cargo_grad     = guild.get_role(cfg['cargo_grad'])
        cargo_mestrado = guild.get_role(cfg['cargo_mestrado'])
        cargo_dout     = guild.get_role(cfg['cargo_dout'])
        cargo_pend     = guild.get_role(cfg['cargo_pendente'])
        todos_nivel    = [r for r in [cargo_pre, cargo_grad, cargo_mestrado, cargo_dout, cargo_pend] if r]

        # Mestrado e Doutorado precisam de formulário
        if escolha in ('mestrado', 'doutorado'):
            if cargo_pend and cargo_pend in member.roles:
                await interaction.response.send_message(
                    '⏳ Você já tem uma solicitação em análise. Aguarde a revisão da equipe.',
                    ephemeral=True)
                return
            nivel_nome = 'Mestrado' if escolha == 'mestrado' else 'Doutorado'
            await interaction.response.send_modal(FormularioAvancado(self.cog, nivel_nome))
            return

        # Pré-Universitário e Graduação são automáticos
        cargo_novo = cargo_pre if escolha == 'pre' else cargo_grad
        if not cargo_novo:
            await interaction.response.send_message(
                '❌ Cargo não configurado. Contate um administrador.', ephemeral=True)
            return

        try:
            para_remover = [r for r in todos_nivel if r in member.roles and r != cargo_novo]
            if para_remover:
                await member.remove_roles(*para_remover, reason='Troca de nível')
            await member.add_roles(cargo_novo, reason='Seleção de nível via bot')
        except discord.Forbidden:
            await interaction.response.send_message(
                '❌ Não tenho permissão para gerenciar cargos.', ephemeral=True)
            return

        nomes = {'pre': 'Pré-Universitário', 'grad': 'Graduação'}
        await interaction.response.send_message(
            f'✅ Cargo **{nomes[escolha]}** atribuído com sucesso!', ephemeral=True)


# ─── View: botão principal "Gerenciar Cargos" ────────────────────────────────

class BotaoGerenciarCargos(discord.ui.View):
    def __init__(self, cog: 'RolesReview'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label='Gerenciar Cargos',
        style=discord.ButtonStyle.primary,
        custom_id='cargos:gerenciar',
        emoji='🎓'
    )
    async def gerenciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SeletorNivel(self.cog)
        await interaction.response.send_message(view=view, ephemeral=True)


# ─── Cog principal ───────────────────────────────────────────────────────────

class RolesReview(commands.Cog, name='Cargos'):
    """Sistema de seleção de cargos com revisão para Mestrado e Doutorado."""

    def __init__(self, bot):
        self.bot = bot
        self.cfg = carregar_config()
        bot.add_view(BotaoGerenciarCargos(self))
        bot.add_view(BotoesRevisao(self, 0))

    @commands.command(name='setup_cargos')
    @commands.has_permissions(administrator=True)
    async def setup_cargos(self, ctx):
        """[Admin] Posta o botão "Gerenciar Cargos" no canal atual.

        Exemplo:
          .setup_cargos
        """
        view = BotaoGerenciarCargos(self)
        await ctx.send(view=view)
        await ctx.message.delete()

    @commands.command(name='config_cargos')
    @commands.has_permissions(administrator=True)
    async def config_cargos(self, ctx,
                             pre: discord.Role,
                             grad: discord.Role,
                             mestrado: discord.Role,
                             doutorado: discord.Role,
                             pendente: discord.Role,
                             canal_revisao: discord.TextChannel):
        """[Admin] Configura os cargos e o canal de revisão.
        Para reconfigurar, basta rodar o comando novamente.

        Uso:
          .config_cargos @Pré-Uni @Graduação @Mestrado @Doutorado @Pendente #canal

        Exemplo:
          .config_cargos @Pré-Universitário @Graduação @Mestrado @Doutorado @Pendente #staff-revisão
        """
        self.cfg.update({
            'cargo_pre':      pre.id,
            'cargo_grad':     grad.id,
            'cargo_mestrado': mestrado.id,
            'cargo_dout':     doutorado.id,
            'cargo_pendente': pendente.id,
            'canal_revisao':  canal_revisao.id,
        })
        salvar_config(self.cfg)

        embed = discord.Embed(title='✅ Configuração Salva!', color=0x2ECC71)
        embed.add_field(name='📘 Pré-Universitário', value=pre.mention,       inline=True)
        embed.add_field(name='📗 Graduação',         value=grad.mention,      inline=True)
        embed.add_field(name='📙 Mestrado',          value=mestrado.mention,  inline=True)
        embed.add_field(name='📕 Doutorado',         value=doutorado.mention, inline=True)
        embed.add_field(name='⏳ Pendente',          value=pendente.mention,  inline=True)
        embed.add_field(name='📨 Canal de Revisão',  value=canal_revisao.mention, inline=True)
        embed.set_footer(text='Para reconfigurar, rode .config_cargos novamente.')
        await ctx.send(embed=embed)

    @commands.command(name='ver_config_cargos')
    @commands.has_permissions(administrator=True)
    async def ver_config_cargos(self, ctx):
        """[Admin] Exibe a configuração atual dos cargos."""
        cfg = self.cfg
        guild = ctx.guild

        def nome_cargo(cid):
            r = guild.get_role(cid)
            return r.mention if r else f'❌ Não configurado (ID: `{cid}`)'

        def nome_canal(cid):
            c = guild.get_channel(cid)
            return c.mention if c else f'❌ Não configurado (ID: `{cid}`)'

        embed = discord.Embed(title='⚙️ Configuração Atual de Cargos', color=0x3498DB)
        embed.add_field(name='📘 Pré-Universitário', value=nome_cargo(cfg['cargo_pre']),      inline=True)
        embed.add_field(name='📗 Graduação',         value=nome_cargo(cfg['cargo_grad']),     inline=True)
        embed.add_field(name='📙 Mestrado',          value=nome_cargo(cfg['cargo_mestrado']), inline=True)
        embed.add_field(name='📕 Doutorado',         value=nome_cargo(cfg['cargo_dout']),     inline=True)
        embed.add_field(name='⏳ Pendente',          value=nome_cargo(cfg['cargo_pendente']), inline=True)
        embed.add_field(name='📨 Canal de Revisão',  value=nome_canal(cfg['canal_revisao']),  inline=True)
        embed.set_footer(text='Use .config_cargos para alterar.')
        await ctx.send(embed=embed)

    @commands.command(name='aprovar')
    @commands.has_permissions(manage_roles=True)
    async def aprovar(self, ctx, membro: discord.Member, *, nivel: str = 'mestrado'):
        """[Staff] Aprova manualmente um membro para Mestrado ou Doutorado.

        Exemplos:
          .aprovar @Usuário mestrado
          .aprovar @Usuário doutorado
        """
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])
        nivel_lower = nivel.lower()

        if 'dout' in nivel_lower:
            cargo_alvo = ctx.guild.get_role(cfg['cargo_dout'])
            nivel_nome = 'Doutorado'
        else:
            cargo_alvo = ctx.guild.get_role(cfg['cargo_mestrado'])
            nivel_nome = 'Mestrado'

        if cargo_pend and cargo_pend in membro.roles:
            await membro.remove_roles(cargo_pend, reason=f'Aprovado por {ctx.author}')
        if cargo_alvo:
            await membro.add_roles(cargo_alvo, reason=f'Aprovado por {ctx.author}')
        try:
            await membro.send(
                f'🎉 Sua solicitação de **{nivel_nome}** foi **aprovada** por {ctx.author} '
                f'no servidor **{ctx.guild.name}**!'
            )
        except discord.Forbidden:
            pass
        await ctx.send(f'✅ {membro.mention} aprovado para **{nivel_nome}**.')

    @commands.command(name='rejeitar')
    @commands.has_permissions(manage_roles=True)
    async def rejeitar(self, ctx, membro: discord.Member, *, nivel: str = 'solicitação'):
        """[Staff] Rejeita manualmente a solicitação de um membro.

        Exemplos:
          .rejeitar @Usuário mestrado
          .rejeitar @Usuário doutorado
        """
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])

        if cargo_pend and cargo_pend in membro.roles:
            await membro.remove_roles(cargo_pend, reason=f'Rejeitado por {ctx.author}')
        try:
            await membro.send(
                f'❌ Sua solicitação de **{nivel}** no servidor **{ctx.guild.name}** '
                f'foi rejeitada por {ctx.author}. Pode tentar novamente ou contatar a equipe.'
            )
        except discord.Forbidden:
            pass
        await ctx.send(f'❌ Solicitação de {membro.mention} rejeitada.')

    @commands.command(name='pendentes')
    @commands.has_permissions(manage_roles=True)
    async def pendentes(self, ctx):
        """[Staff] Lista membros com o cargo Pendente."""
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])
        if not cargo_pend:
            return await ctx.send('❌ Cargo "Pendente" não configurado.')

        membros = [m for m in ctx.guild.members if cargo_pend in m.roles]
        if not membros:
            return await ctx.send('📭 Nenhum membro aguardando revisão.')

        embed = discord.Embed(title=f'⏳ Pendentes de Revisão ({len(membros)})', color=0xFEE75C)
        lista = '\n'.join([f'• {m.mention} (`{m.id}`)' for m in membros[:20]])
        embed.description = lista
        if len(membros) > 20:
            embed.set_footer(text=f'Mostrando 20 de {len(membros)}')
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RolesReview(bot))
