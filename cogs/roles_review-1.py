"""
Cog de Seleção de Cargos com Revisão.

Fluxo:
  - Um admin usa .setup_cargos para postar o botão "Gerenciar Cargos" no canal.
  - Usuário clica → escolhe seu nível.
  - Pré-Universitário / Graduação → cargo dado imediatamente.
  - Pós-Graduação → abre formulário (modal) → dá cargo "Pendente (Pós)" →
    manda respostas pro canal de staff com botões Aprovar / Rejeitar.
  - Staff aprova → remove "Pendente (Pós)" e dá "Pós-Graduação".
  - Staff rejeita → remove "Pendente (Pós)" e notifica o usuário.

Configuração (variáveis de ambiente ou comando .config_cargos):
  CARGO_PRE_UNIVERSITARIO  → ID do cargo Pré-Universitário
  CARGO_GRADUACAO          → ID do cargo Graduação
  CARGO_POS_GRADUACAO      → ID do cargo Pós-Graduação
  CARGO_PENDENTE_POS       → ID do cargo Pendente (Pós)
  CANAL_REVISAO            → ID do canal de staff/revisão
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
from pathlib import Path

log = logging.getLogger('cogs.roles_review')

CONFIG_FILE = Path('data/roles_config.json')

# ─── Perguntas do formulário de Pós-Graduação ────────────────────────────────
PERGUNTAS_POS = [
    ("qual_matematica",   "Em qual área da matemática você tem interesse?",
     "Ex: Topologia, Álgebra Abstrata, Análise Real... Pode ser amplo!"),
    ("background",        "Qual é a sua formação/background educacional?",
     "Responda só se se sentir confortável. Ex: cursando doutorado em..."),
    ("papers_livros",     "Quais papers ou livros de matemática você leu recentemente?",
     "Nos conte o que achou interessante!"),
]

# ─── Helpers de config ───────────────────────────────────────────────────────

def _cfg_default() -> dict:
    return {
        "cargo_pre":       int(os.environ.get("CARGO_PRE_UNIVERSITARIO", 0)),
        "cargo_grad":      int(os.environ.get("CARGO_GRADUACAO", 0)),
        "cargo_pos":       int(os.environ.get("CARGO_POS_GRADUACAO", 0)),
        "cargo_pendente":  int(os.environ.get("CARGO_PENDENTE_POS", 0)),
        "canal_revisao":   int(os.environ.get("CANAL_REVISAO", 0)),
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


# ─── Modal: formulário de Pós-Graduação ──────────────────────────────────────

class FormularioPosGrad(discord.ui.Modal, title='Solicitação — Pós-Graduação'):
    qual_matematica = discord.ui.TextInput(
        label='Qual área da matemática te interessa?',
        placeholder='Ex: Topologia, Álgebra, Análise Real... Pode ser amplo!',
        style=discord.TextStyle.paragraph,
        max_length=600,
        required=True,
    )
    background = discord.ui.TextInput(
        label='Qual é sua formação/background?',
        placeholder='Responda só se quiser. Ex: cursando doutorado em...',
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

    def __init__(self, cog: 'RolesReview'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        cfg = self.cog.cfg
        guild = interaction.guild
        member = interaction.user

        # Dar cargo "Pendente (Pós)"
        cargo_pendente = guild.get_role(cfg['cargo_pendente'])
        cargos_nivel = [
            guild.get_role(cfg['cargo_pre']),
            guild.get_role(cfg['cargo_grad']),
            guild.get_role(cfg['cargo_pos']),
        ]

        try:
            # Remove outros cargos de nível se existirem
            para_remover = [r for r in cargos_nivel if r and r in member.roles]
            if para_remover:
                await member.remove_roles(*para_remover, reason='Troca de nível')

            if cargo_pendente:
                await member.add_roles(cargo_pendente, reason='Aguardando revisão Pós-Graduação')
        except discord.Forbidden:
            await interaction.response.send_message(
                '❌ Não tenho permissão para gerenciar cargos. Contate um administrador.', ephemeral=True)
            return

        # Confirmação para o usuário
        await interaction.response.send_message(
            '✅ **Formulário enviado!** Você recebeu o cargo **Pendente (Pós)** enquanto a equipe avalia sua solicitação. '
            'Você será notificado assim que houver uma decisão.',
            ephemeral=True
        )

        # Mandar para canal de revisão
        canal = guild.get_channel(cfg['canal_revisao'])
        if not canal:
            log.warning(f'Canal de revisão não configurado ou não encontrado (ID: {cfg["canal_revisao"]})')
            return

        embed = discord.Embed(
            title='📋 Nova Solicitação — Pós-Graduação',
            color=0x9B59B6,
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name='Usuário', value=f'{member.mention} (`{member.id}`)', inline=False)
        embed.add_field(
            name='🔬 Área de interesse em matemática',
            value=self.qual_matematica.value or '*(não respondido)*',
            inline=False
        )
        embed.add_field(
            name='🎓 Formação/background',
            value=self.background.value or '*(não respondido)*',
            inline=False
        )
        embed.add_field(
            name='📚 Papers/livros recentes',
            value=self.papers_livros.value or '*(não respondido)*',
            inline=False
        )
        embed.set_footer(text=f'ID do membro: {member.id}')

        view = BotoesRevisao(self.cog, member.id)
        await canal.send(embed=embed, view=view)


# ─── View: botões de revisão para staff ──────────────────────────────────────

class BotoesRevisao(discord.ui.View):
    def __init__(self, cog: 'RolesReview', user_id: int):
        super().__init__(timeout=None)  # Persistente
        self.cog = cog
        self.user_id = user_id

    @discord.ui.button(label='✅ Aprovar', style=discord.ButtonStyle.success, custom_id='revisao:aprovar')
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._processar(interaction, aprovado=True)

    @discord.ui.button(label='❌ Rejeitar', style=discord.ButtonStyle.danger, custom_id='revisao:rejeitar')
    async def rejeitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._processar(interaction, aprovado=False)

    async def _processar(self, interaction: discord.Interaction, aprovado: bool):
        cfg = self.cog.cfg
        guild = interaction.guild

        # Verificar permissão de staff
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message('❌ Você não tem permissão para revisar solicitações.', ephemeral=True)
            return

        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message('❌ Usuário não encontrado no servidor (pode ter saído).', ephemeral=True)
            self._desabilitar_botoes()
            await interaction.message.edit(view=self)
            return

        cargo_pendente = guild.get_role(cfg['cargo_pendente'])
        cargo_pos      = guild.get_role(cfg['cargo_pos'])

        try:
            if cargo_pendente and cargo_pendente in member.roles:
                await member.remove_roles(cargo_pendente, reason=f'Revisão por {interaction.user}')

            if aprovado:
                if cargo_pos:
                    await member.add_roles(cargo_pos, reason=f'Aprovado por {interaction.user}')
                # Notificar usuário
                try:
                    await member.send(
                        f'🎉 **Parabéns!** Sua solicitação para o cargo **Pós-Graduação** foi **aprovada** '
                        f'por {interaction.user.mention} no servidor **{guild.name}**!'
                    )
                except discord.Forbidden:
                    pass
            else:
                # Notificar usuário
                try:
                    await member.send(
                        f'❌ Sua solicitação para o cargo **Pós-Graduação** no servidor **{guild.name}** '
                        f'foi **rejeitada** por {interaction.user.mention}. '
                        f'Você pode tentar novamente ou entrar em contato com a equipe.'
                    )
                except discord.Forbidden:
                    pass

        except discord.Forbidden:
            await interaction.response.send_message('❌ Não tenho permissão para gerenciar cargos.', ephemeral=True)
            return

        # Atualizar embed
        embed = interaction.message.embeds[0]
        status = '✅ APROVADO' if aprovado else '❌ REJEITADO'
        cor    = 0x2ECC71 if aprovado else 0xED4245
        embed.color = cor
        embed.set_footer(text=f'{status} por {interaction.user} | ID: {self.user_id}')

        self._desabilitar_botoes()
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f'{"✅ Aprovado" if aprovado else "❌ Rejeitado"}: {member.mention}', ephemeral=True
        )

    def _desabilitar_botoes(self):
        for item in self.children:
            item.disabled = True


# ─── View: seletor de nível (botão "Gerenciar Cargos") ───────────────────────

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
                description='Ensino fundamental/médio, vestibulandos, olimpíadas.',
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
                label='Pós-Graduação',
                description='Mestrado, doutorado ou pesquisador. Requer revisão.',
                emoji='📕',
                value='pos',
            ),
        ]
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        escolha = select.values[0]
        cfg = self.cog.cfg
        guild = interaction.guild
        member = interaction.user

        cargo_pre  = guild.get_role(cfg['cargo_pre'])
        cargo_grad = guild.get_role(cfg['cargo_grad'])
        cargo_pos  = guild.get_role(cfg['cargo_pos'])
        cargo_pend = guild.get_role(cfg['cargo_pendente'])

        # Cargos de nível para remover antes de atribuir novo
        todos_nivel = [r for r in [cargo_pre, cargo_grad, cargo_pos, cargo_pend] if r]

        if escolha == 'pos':
            # Verifica se já está pendente
            if cargo_pend and cargo_pend in member.roles:
                await interaction.response.send_message(
                    '⏳ Você já tem uma solicitação de **Pós-Graduação** em análise. Aguarde a revisão da equipe.',
                    ephemeral=True
                )
                return
            # Abre formulário
            await interaction.response.send_modal(FormularioPosGrad(self.cog))
            return

        # Cargos automáticos (Pré / Graduação)
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
            f'✅ Cargo **{nomes[escolha]}** atribuído com sucesso!', ephemeral=True
        )


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
        await interaction.response.send_message(
            '**Selecione seu nível de matemática:**\n'
            '> 📘 **Pré-Universitário** — Ensino médio, vestibular, olimpíadas\n'
            '> 📗 **Graduação** — Cursando ou graduado no ensino superior\n'
            '> 📕 **Pós-Graduação** — Mestrado/doutorado *(requer formulário e revisão da equipe)*',
            view=view,
            ephemeral=True
        )


# ─── Cog principal ───────────────────────────────────────────────────────────

class RolesReview(commands.Cog, name='Cargos'):
    """Sistema de seleção de cargos com revisão para Pós-Graduação."""

    def __init__(self, bot):
        self.bot = bot
        self.cfg = carregar_config()
        # Registrar views persistentes (sobrevivem a restart)
        bot.add_view(BotaoGerenciarCargos(self))
        bot.add_view(BotoesRevisao(self, 0))  # user_id=0 como placeholder

    # ─── Setup ───────────────────────────────────────────────────────────────

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

    # ─── Configuração de IDs ─────────────────────────────────────────────────

    @commands.command(name='config_cargos')
    @commands.has_permissions(administrator=True)
    async def config_cargos(self, ctx,
                             pre: discord.Role,
                             grad: discord.Role,
                             pos: discord.Role,
                             pendente: discord.Role,
                             canal_revisao: discord.TextChannel):
        """[Admin] Configura os cargos e o canal de revisão.

        Uso:
          .config_cargos @Pré-Universitário @Graduação @Pós-Graduação @Pendente-Pós #canal-revisão

        Exemplo:
          .config_cargos @Pre @Grad @Pos @PendentePós #staff-revisão
        """
        self.cfg.update({
            'cargo_pre':      pre.id,
            'cargo_grad':     grad.id,
            'cargo_pos':      pos.id,
            'cargo_pendente': pendente.id,
            'canal_revisao':  canal_revisao.id,
        })
        salvar_config(self.cfg)

        embed = discord.Embed(title='✅ Configuração de Cargos Salva', color=0x2ECC71)
        embed.add_field(name='Pré-Universitário', value=pre.mention, inline=True)
        embed.add_field(name='Graduação',         value=grad.mention, inline=True)
        embed.add_field(name='Pós-Graduação',     value=pos.mention, inline=True)
        embed.add_field(name='Pendente (Pós)',    value=pendente.mention, inline=True)
        embed.add_field(name='Canal de Revisão',  value=canal_revisao.mention, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='ver_config_cargos')
    @commands.has_permissions(administrator=True)
    async def ver_config_cargos(self, ctx):
        """[Admin] Exibe a configuração atual dos cargos."""
        cfg = self.cfg
        guild = ctx.guild

        def nome_cargo(cid):
            r = guild.get_role(cid)
            return r.mention if r else f'❌ Não encontrado (ID: `{cid}`)'

        def nome_canal(cid):
            c = guild.get_channel(cid)
            return c.mention if c else f'❌ Não encontrado (ID: `{cid}`)'

        embed = discord.Embed(title='⚙️ Configuração de Cargos', color=0x3498DB)
        embed.add_field(name='Pré-Universitário', value=nome_cargo(cfg['cargo_pre']),      inline=True)
        embed.add_field(name='Graduação',         value=nome_cargo(cfg['cargo_grad']),     inline=True)
        embed.add_field(name='Pós-Graduação',     value=nome_cargo(cfg['cargo_pos']),      inline=True)
        embed.add_field(name='Pendente (Pós)',    value=nome_cargo(cfg['cargo_pendente']), inline=True)
        embed.add_field(name='Canal de Revisão',  value=nome_canal(cfg['canal_revisao']),  inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='aprovar_pos')
    @commands.has_permissions(manage_roles=True)
    async def aprovar_pos(self, ctx, membro: discord.Member):
        """[Staff] Aprova manualmente um membro para Pós-Graduação.

        Exemplo:
          .aprovar_pos @Usuário
        """
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])
        cargo_pos  = ctx.guild.get_role(cfg['cargo_pos'])

        if cargo_pend and cargo_pend in membro.roles:
            await membro.remove_roles(cargo_pend, reason=f'Aprovado por {ctx.author}')
        if cargo_pos:
            await membro.add_roles(cargo_pos, reason=f'Aprovado por {ctx.author}')
        try:
            await membro.send(f'🎉 Sua solicitação de **Pós-Graduação** foi **aprovada** por {ctx.author} no servidor **{ctx.guild.name}**!')
        except discord.Forbidden:
            pass
        await ctx.send(f'✅ {membro.mention} aprovado para **Pós-Graduação**.')

    @commands.command(name='rejeitar_pos')
    @commands.has_permissions(manage_roles=True)
    async def rejeitar_pos(self, ctx, membro: discord.Member):
        """[Staff] Rejeita manualmente a solicitação de Pós-Graduação de um membro.

        Exemplo:
          .rejeitar_pos @Usuário
        """
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])

        if cargo_pend and cargo_pend in membro.roles:
            await membro.remove_roles(cargo_pend, reason=f'Rejeitado por {ctx.author}')
        try:
            await membro.send(
                f'❌ Sua solicitação de **Pós-Graduação** no servidor **{ctx.guild.name}** '
                f'foi rejeitada por {ctx.author}. Pode tentar novamente ou contatar a equipe.'
            )
        except discord.Forbidden:
            pass
        await ctx.send(f'❌ Solicitação de {membro.mention} rejeitada.')

    @commands.command(name='pendentes_pos')
    @commands.has_permissions(manage_roles=True)
    async def pendentes_pos(self, ctx):
        """[Staff] Lista membros com o cargo Pendente (Pós)."""
        cfg = self.cfg
        cargo_pend = ctx.guild.get_role(cfg['cargo_pendente'])
        if not cargo_pend:
            return await ctx.send('❌ Cargo "Pendente (Pós)" não configurado.')

        membros = [m for m in ctx.guild.members if cargo_pend in m.roles]
        if not membros:
            return await ctx.send('📭 Nenhum membro aguardando revisão.')

        embed = discord.Embed(
            title=f'⏳ Pendentes de Revisão ({len(membros)})',
            color=0xFEE75C
        )
        lista = '\n'.join([f'• {m.mention} (`{m.id}`)' for m in membros[:20]])
        embed.description = lista
        if len(membros) > 20:
            embed.set_footer(text=f'Mostrando 20 de {len(membros)}')
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RolesReview(bot))
