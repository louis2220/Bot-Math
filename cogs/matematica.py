"""
Cog de Matemática — comandos matemáticos principais.
Utiliza SymPy para cálculos simbólicos.
"""

import discord
from discord.ext import commands
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application
)
import io
import logging
import traceback

log = logging.getLogger('cogs.matematica')

TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

# Variáveis simbólicas comuns
x, y, z, t, n = sp.symbols('x y z t n')
a, b, c = sp.symbols('a b c')

VARIAVEIS = {
    'x': x, 'y': y, 'z': z, 't': t, 'n': n,
    'a': a, 'b': b, 'c': c,
    'pi': sp.pi, 'e': sp.E, 'oo': sp.oo, 'inf': sp.oo,
    'I': sp.I, 'i': sp.I,
}


def parse_expressao(texto: str):
    """Converte string em expressão SymPy."""
    return parse_expr(texto, local_dict=VARIAVEIS, transformations=TRANSFORMATIONS)


def formatar_resultado(expr) -> str:
    """Formata um resultado SymPy de forma legível."""
    if isinstance(expr, (list, tuple)):
        partes = [sp.pretty(e, use_unicode=True) for e in expr]
        return '\n'.join(partes)
    return sp.pretty(expr, use_unicode=True)


class Matematica(commands.Cog, name='Matemática'):
    """Comandos matemáticos: cálculo, álgebra, combinatória e mais."""

    def __init__(self, bot):
        self.bot = bot

    # ─── CALCULAR ────────────────────────────────────────────────────────────

    @commands.command(name='calc', aliases=['calcular', 'c'])
    async def calcular(self, ctx, *, expressao: str):
        """Calcula uma expressão matemática.

        Exemplos:
          .calc 2 + 2
          .calc sqrt(16)
          .calc (3 + 4i) * (1 - 2i)
          .calc pi * 5**2
        """
        try:
            expr = parse_expressao(expressao)
            resultado = sp.simplify(expr)
            resultado_num = None

            if resultado.is_number:
                resultado_num = float(resultado.evalf())

            embed = discord.Embed(title='🧮 Calculadora', color=0x5865F2)
            embed.add_field(name='Expressão', value=f'```{expressao}```', inline=False)
            embed.add_field(name='Resultado (simplificado)', value=f'```{formatar_resultado(resultado)}```', inline=False)

            if resultado_num is not None and str(resultado) != str(resultado_num):
                embed.add_field(name='Valor numérico', value=f'```{resultado_num:.10g}```', inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Expressão inválida: `{e}`')

    # ─── SIMPLIFICAR ─────────────────────────────────────────────────────────

    @commands.command(name='simplificar', aliases=['simp', 'simplify'])
    async def simplificar(self, ctx, *, expressao: str):
        """Simplifica uma expressão algébrica.

        Exemplos:
          .simplificar (x**2 - 1) / (x - 1)
          .simplificar sin(x)**2 + cos(x)**2
          .simplificar (a+b)**2 - (a**2 + 2*a*b + b**2)
        """
        try:
            expr = parse_expressao(expressao)
            resultado = sp.simplify(expr)

            embed = discord.Embed(title='✏️ Simplificar', color=0x57F287)
            embed.add_field(name='Original', value=f'```{formatar_resultado(expr)}```', inline=False)
            embed.add_field(name='Simplificado', value=f'```{formatar_resultado(resultado)}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Não foi possível simplificar: `{e}`')

    # ─── EXPANDIR ────────────────────────────────────────────────────────────

    @commands.command(name='expandir', aliases=['expand'])
    async def expandir(self, ctx, *, expressao: str):
        """Expande uma expressão algébrica.

        Exemplos:
          .expandir (x + 2)**3
          .expandir (a - b)*(a + b)
          .expandir (x + 1)*(x + 2)*(x + 3)
        """
        try:
            expr = parse_expressao(expressao)
            resultado = sp.expand(expr)

            embed = discord.Embed(title='📐 Expandir', color=0xFEE75C)
            embed.add_field(name='Original', value=f'```{formatar_resultado(expr)}```', inline=False)
            embed.add_field(name='Expandido', value=f'```{formatar_resultado(resultado)}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── FATORAR ─────────────────────────────────────────────────────────────

    @commands.command(name='fatorar', aliases=['fatoracao', 'fatorização', 'factor'])
    async def fatorar(self, ctx, *, expressao: str):
        """Fatoriza uma expressão polinomial.

        Exemplos:
          .fatorar x**2 - 5*x + 6
          .fatorar x**3 - 1
          .fatorar 12
          .fatorar x**4 - 16
        """
        try:
            expr = parse_expressao(expressao)
            resultado = sp.factor(expr)

            embed = discord.Embed(title='🔢 Fatorar', color=0xEB459E)
            embed.add_field(name='Original', value=f'```{formatar_resultado(expr)}```', inline=False)
            embed.add_field(name='Fatorado', value=f'```{formatar_resultado(resultado)}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── RESOLVER EQUAÇÃO ────────────────────────────────────────────────────

    @commands.command(name='resolver', aliases=['resolve', 'solve', 'equacao', 'equação'])
    async def resolver(self, ctx, *, entrada: str):
        """Resolve uma equação em relação a x (ou outra variável).

        Uso:
          .resolver <equação> [em <variável>]

        Exemplos:
          .resolver x**2 - 5*x + 6 = 0
          .resolver 2*x + 3 = 7
          .resolver x**3 = 8
          .resolver a*x + b = 0 em x
        """
        try:
            # Detectar variável (ex: "em y")
            var = x
            if ' em ' in entrada.lower():
                partes = entrada.lower().split(' em ')
                entrada = entrada[:len(partes[0])]
                nome_var = partes[1].strip()
                var = VARIAVEIS.get(nome_var, sp.Symbol(nome_var))

            # Detectar equação (com =)
            if '=' in entrada:
                lado_esq, lado_dir = entrada.split('=', 1)
                expr_esq = parse_expressao(lado_esq.strip())
                expr_dir = parse_expressao(lado_dir.strip())
                equacao = sp.Eq(expr_esq, expr_dir)
            else:
                expr = parse_expressao(entrada)
                equacao = sp.Eq(expr, 0)

            solucoes = sp.solve(equacao, var)

            embed = discord.Embed(title='🔍 Resolver Equação', color=0xED4245)
            embed.add_field(name='Equação', value=f'```{equacao}```', inline=False)

            if not solucoes:
                embed.add_field(name='Soluções', value='Sem solução real.', inline=False)
            else:
                sol_str = '\n'.join([f'  {var} = {formatar_resultado(s)}' for s in solucoes])
                embed.add_field(name=f'Soluções ({len(solucoes)})', value=f'```{sol_str}```', inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro ao resolver: `{e}`')

    # ─── SISTEMA DE EQUAÇÕES ─────────────────────────────────────────────────

    @commands.command(name='sistema', aliases=['sis', 'sistema_eq'])
    async def sistema(self, ctx, *, entrada: str):
        """Resolve um sistema de equações. Separe as equações com `;`.

        Exemplos:
          .sistema x + y = 5; x - y = 1
          .sistema 2*x + y = 7; x + 3*y = 11
        """
        try:
            linhas = [l.strip() for l in entrada.split(';')]
            equacoes = []
            variaveis_detectadas = set()

            for linha in linhas:
                if '=' in linha:
                    esq, dir_ = linha.split('=', 1)
                    e1 = parse_expressao(esq.strip())
                    e2 = parse_expressao(dir_.strip())
                    eq = sp.Eq(e1, e2)
                    equacoes.append(eq)
                    variaveis_detectadas |= e1.free_symbols | e2.free_symbols
                else:
                    e = parse_expressao(linha)
                    equacoes.append(sp.Eq(e, 0))
                    variaveis_detectadas |= e.free_symbols

            variaveis_list = sorted(variaveis_detectadas, key=str)
            solucoes = sp.solve(equacoes, variaveis_list)

            embed = discord.Embed(title='📊 Sistema de Equações', color=0x9B59B6)
            eq_str = '\n'.join([str(e) for e in equacoes])
            embed.add_field(name='Sistema', value=f'```{eq_str}```', inline=False)

            if not solucoes:
                embed.add_field(name='Resultado', value='Sem solução ou infinitas soluções.', inline=False)
            elif isinstance(solucoes, dict):
                sol_str = '\n'.join([f'  {k} = {formatar_resultado(v)}' for k, v in solucoes.items()])
                embed.add_field(name='Solução', value=f'```{sol_str}```', inline=False)
            else:
                embed.add_field(name='Soluções', value=f'```{solucoes}```', inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── DERIVADA ────────────────────────────────────────────────────────────

    @commands.command(name='derivada', aliases=['deriv', 'diff', 'diferencial'])
    async def derivada(self, ctx, *, entrada: str):
        """Calcula a derivada de uma expressão.

        Uso:
          .derivada <expressão> [em <variável>] [ordem <n>]

        Exemplos:
          .derivada x**3 + 2*x
          .derivada sin(x) * cos(x)
          .derivada x**5 ordem 2
          .derivada x*y**2 em y
        """
        try:
            var = x
            ordem = 1

            if ' ordem ' in entrada.lower():
                partes = entrada.lower().split(' ordem ')
                entrada = entrada[:len(partes[0])].strip()
                ordem = int(partes[1].strip())

            if ' em ' in entrada.lower():
                partes = entrada.lower().split(' em ')
                entrada = entrada[:len(partes[0])].strip()
                nome_var = partes[1].strip()
                var = VARIAVEIS.get(nome_var, sp.Symbol(nome_var))

            expr = parse_expressao(entrada)
            resultado = sp.diff(expr, var, ordem)
            resultado_simpl = sp.simplify(resultado)

            embed = discord.Embed(title='📉 Derivada', color=0x1ABC9C)
            embed.add_field(name='Função', value=f'```f = {formatar_resultado(expr)}```', inline=False)
            embed.add_field(
                name=f"d{'ⁿ' if ordem > 1 else ''}f/d{var}{'ⁿ' if ordem > 1 else ''} (ordem {ordem})",
                value=f'```{formatar_resultado(resultado_simpl)}```',
                inline=False
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── INTEGRAL ────────────────────────────────────────────────────────────

    @commands.command(name='integral', aliases=['integrar', 'integ'])
    async def integral(self, ctx, *, entrada: str):
        """Calcula a integral indefinida ou definida.

        Uso:
          .integral <expressão> [em <variável>] [de <a> até <b>]

        Exemplos:
          .integral x**2
          .integral sin(x) em x
          .integral x**2 de 0 até 3
          .integral cos(x) de 0 até pi
        """
        try:
            var = x
            a_val = None
            b_val = None

            if ' de ' in entrada.lower() and ' até ' in entrada.lower():
                idx_de = entrada.lower().index(' de ')
                idx_ate = entrada.lower().index(' até ')
                expr_str = entrada[:idx_de].strip()
                a_str = entrada[idx_de+4:idx_ate].strip()
                b_str = entrada[idx_ate+5:].strip()
                a_val = parse_expressao(a_str)
                b_val = parse_expressao(b_str)
                entrada = expr_str

            if ' em ' in entrada.lower():
                partes = entrada.lower().split(' em ')
                entrada = entrada[:len(partes[0])].strip()
                nome_var = partes[1].strip()
                var = VARIAVEIS.get(nome_var, sp.Symbol(nome_var))

            expr = parse_expressao(entrada)

            if a_val is not None and b_val is not None:
                resultado = sp.integrate(expr, (var, a_val, b_val))
                tipo = f'de {a_val} até {b_val}'
            else:
                resultado = sp.integrate(expr, var)
                tipo = 'indefinida'

            resultado_simpl = sp.simplify(resultado)

            embed = discord.Embed(title='∫ Integral', color=0xE67E22)
            embed.add_field(name='Função', value=f'```f = {formatar_resultado(expr)}```', inline=False)
            embed.add_field(
                name=f'Integral ({tipo})',
                value=f'```{formatar_resultado(resultado_simpl)}{"  + C" if tipo == "indefinida" else ""}```',
                inline=False
            )
            if tipo != 'indefinida' and resultado_simpl.is_number:
                embed.add_field(
                    name='Valor numérico',
                    value=f'```≈ {float(resultado_simpl.evalf()):.10g}```',
                    inline=False
                )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── LIMITE ──────────────────────────────────────────────────────────────

    @commands.command(name='limite', aliases=['lim', 'limit'])
    async def limite(self, ctx, *, entrada: str):
        """Calcula o limite de uma expressão.

        Uso:
          .limite <expressão> quando <variável> -> <valor>

        Exemplos:
          .limite sin(x)/x quando x -> 0
          .limite (1 + 1/n)**n quando n -> oo
          .limite (x**2 - 1)/(x - 1) quando x -> 1
        """
        try:
            if ' quando ' not in entrada.lower():
                return await ctx.send('❌ Use o formato: `.limite <expressão> quando <var> -> <valor>`')

            idx = entrada.lower().index(' quando ')
            expr_str = entrada[:idx].strip()
            resto = entrada[idx+8:].strip()

            if '->' not in resto:
                return await ctx.send('❌ Use `->` para indicar o valor. Ex: `x -> 0`')

            var_str, val_str = resto.split('->', 1)
            var_lim = VARIAVEIS.get(var_str.strip(), sp.Symbol(var_str.strip()))
            val_lim = parse_expressao(val_str.strip())

            expr = parse_expressao(expr_str)
            resultado = sp.limit(expr, var_lim, val_lim)

            embed = discord.Embed(title='📏 Limite', color=0x3498DB)
            embed.add_field(name='Expressão', value=f'```{formatar_resultado(expr)}```', inline=False)
            embed.add_field(name=f'lim ({var_lim} → {val_lim})', value=f'```{formatar_resultado(resultado)}```', inline=False)
            if resultado.is_number:
                embed.add_field(name='Valor numérico', value=f'```≈ {float(resultado.evalf()):.10g}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── COMBINATÓRIA ────────────────────────────────────────────────────────

    @commands.command(name='combinacao', aliases=['comb', 'C'])
    async def combinacao(self, ctx, n_val: int, r_val: int):
        """Calcula C(n, r) — combinações.

        Exemplos:
          .combinacao 10 3
          .comb 52 5
        """
        try:
            resultado = sp.binomial(n_val, r_val)
            embed = discord.Embed(title='🎲 Combinação', color=0x2ECC71)
            embed.add_field(name='C(n, r)', value=f'C({n_val}, {r_val})', inline=True)
            embed.add_field(name='Resultado', value=f'**{resultado}**', inline=True)
            embed.set_footer(text=f'Fórmula: n! / (r! × (n-r)!)')
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    @commands.command(name='permutacao', aliases=['perm', 'P'])
    async def permutacao(self, ctx, n_val: int, r_val: int = None):
        """Calcula P(n, r) — permutações, ou n! se r não for dado.

        Exemplos:
          .permutacao 5 3
          .perm 7
        """
        try:
            if r_val is None:
                resultado = sp.factorial(n_val)
                titulo = f'P({n_val}) = {n_val}!'
            else:
                resultado = int(sp.factorial(n_val) / sp.factorial(n_val - r_val))
                titulo = f'P({n_val}, {r_val})'

            embed = discord.Embed(title='🎰 Permutação', color=0x9B59B6)
            embed.add_field(name='Expressão', value=titulo, inline=True)
            embed.add_field(name='Resultado', value=f'**{resultado}**', inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    @commands.command(name='fatorial', aliases=['fat', 'factorial'])
    async def fatorial(self, ctx, n_val: int):
        """Calcula o fatorial de n.

        Exemplos:
          .fatorial 10
          .fat 20
        """
        if n_val < 0:
            return await ctx.send('❌ Fatorial não definido para negativos.')
        if n_val > 1000:
            return await ctx.send('❌ Número muito grande (máx: 1000).')
        resultado = sp.factorial(n_val)
        embed = discord.Embed(title='❗ Fatorial', color=0xF39C12)
        embed.add_field(name='n', value=str(n_val), inline=True)
        embed.add_field(name='n!', value=f'**{resultado}**', inline=True)
        await ctx.send(embed=embed)

    # ─── NÚMEROS ─────────────────────────────────────────────────────────────

    @commands.command(name='primo', aliases=['primalidade', 'ehprimo'])
    async def primo(self, ctx, n_val: int):
        """Verifica se um número é primo.

        Exemplos:
          .primo 17
          .primo 100
        """
        resultado = sp.isprime(n_val)
        if resultado:
            embed = discord.Embed(title='🔵 Número Primo', description=f'**{n_val}** é primo! ✅', color=0x2ECC71)
        else:
            fatores = sp.factorint(n_val)
            fat_str = ' × '.join([f'{p}^{e}' if e > 1 else str(p) for p, e in fatores.items()])
            embed = discord.Embed(title='🔴 Não é Primo', description=f'**{n_val}** não é primo. ❌', color=0xED4245)
            embed.add_field(name='Fatoração', value=f'```{n_val} = {fat_str}```')
        await ctx.send(embed=embed)

    @commands.command(name='mdc', aliases=['gcd', 'mmc', 'lcm'])
    async def mdc_mmc(self, ctx, *numeros: int):
        """Calcula o MDC e MMC de dois ou mais números.

        Exemplos:
          .mdc 12 18
          .mdc 12 18 24
        """
        if len(numeros) < 2:
            return await ctx.send('❌ Forneça ao menos 2 números.')

        mdc = numeros[0]
        mmc = numeros[0]
        for n_num in numeros[1:]:
            mdc = sp.gcd(mdc, n_num)
            mmc = sp.lcm(mmc, n_num)

        embed = discord.Embed(title='🔢 MDC e MMC', color=0x16A085)
        embed.add_field(name='Números', value=' | '.join(map(str, numeros)), inline=False)
        embed.add_field(name='MDC (Máximo Divisor Comum)', value=f'**{mdc}**', inline=True)
        embed.add_field(name='MMC (Mínimo Múltiplo Comum)', value=f'**{mmc}**', inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='divisores', aliases=['divs'])
    async def divisores(self, ctx, n_val: int):
        """Lista todos os divisores de n.

        Exemplos:
          .divisores 36
          .divisores 100
        """
        if n_val <= 0:
            return await ctx.send('❌ Número deve ser positivo.')
        if n_val > 10**7:
            return await ctx.send('❌ Número muito grande (máx: 10.000.000).')

        divs = sp.divisors(n_val)
        embed = discord.Embed(title='📋 Divisores', color=0x27AE60)
        embed.add_field(name='Número', value=str(n_val), inline=True)
        embed.add_field(name='Quantidade', value=str(len(divs)), inline=True)
        embed.add_field(name='Divisores', value=f'```{", ".join(map(str, divs))}```', inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='fatorar_inteiro', aliases=['fatint', 'primos'])
    async def fatorar_inteiro(self, ctx, n_val: int):
        """Fatoriza um número inteiro em fatores primos.

        Exemplos:
          .fatint 360
          .primos 1024
        """
        if n_val <= 1:
            return await ctx.send('❌ Número deve ser maior que 1.')
        if n_val > 10**15:
            return await ctx.send('❌ Número muito grande.')

        fatores = sp.factorint(n_val)
        fat_str = ' × '.join([f'{p}^{e}' if e > 1 else str(p) for p, e in fatores.items()])

        embed = discord.Embed(title='🧩 Fatoração em Primos', color=0xE74C3C)
        embed.add_field(name='Número', value=str(n_val), inline=True)
        embed.add_field(name='Fatoração', value=f'```{n_val} = {fat_str}```', inline=False)
        primos_list = [str(p) for p in fatores.keys()]
        embed.add_field(name='Fatores primos', value=', '.join(primos_list), inline=False)
        await ctx.send(embed=embed)

    # ─── MATRIZES ────────────────────────────────────────────────────────────

    @commands.command(name='matriz', aliases=['mat'])
    async def matriz(self, ctx, *, entrada: str):
        """Operações com matrizes. Linhas separadas por `;`, elementos por `,`.

        Subcomandos: det, inv, rank, transposta
        Uso:
          .matriz det [[1,2],[3,4]]
          .matriz inv [[1,2],[3,4]]
          .matriz transposta [[1,2,3],[4,5,6]]
          .matriz rank [[1,2,3],[4,5,6]]

        Formato: `[[a,b],[c,d]]`
        """
        try:
            partes = entrada.split(None, 1)
            if len(partes) < 2:
                return await ctx.send('❌ Uso: `.matriz <operação> <matriz>`')

            operacao = partes[0].lower()
            mat_str = partes[1].strip()
            dados = eval(mat_str)  # Converte string em lista Python
            M = sp.Matrix(dados)

            embed = discord.Embed(title='🧮 Matriz', color=0x8E44AD)
            embed.add_field(name='Matriz', value=f'```{M}```', inline=False)

            if operacao == 'det':
                resultado = M.det()
                embed.add_field(name='Determinante', value=f'```{formatar_resultado(resultado)}```', inline=False)
            elif operacao == 'inv':
                if M.det() == 0:
                    embed.add_field(name='Inversa', value='❌ Matriz singular (det = 0), não tem inversa.', inline=False)
                else:
                    inv = M.inv()
                    embed.add_field(name='Inversa', value=f'```{inv}```', inline=False)
            elif operacao in ('transposta', 'T'):
                t_mat = M.T
                embed.add_field(name='Transposta', value=f'```{t_mat}```', inline=False)
            elif operacao == 'rank':
                rank = M.rank()
                embed.add_field(name='Rank', value=f'**{rank}**', inline=False)
            elif operacao in ('autovalores', 'eigenvalues'):
                avs = M.eigenvals()
                av_str = '\n'.join([f'λ = {v}: multiplicidade {m}' for v, m in avs.items()])
                embed.add_field(name='Autovalores', value=f'```{av_str}```', inline=False)
            else:
                embed.add_field(name='Operações disponíveis', value='`det`, `inv`, `transposta`, `rank`, `autovalores`', inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`\n💡 Formato correto: `[[1,2],[3,4]]`')

    # ─── SEQUÊNCIAS ──────────────────────────────────────────────────────────

    @commands.command(name='sequencia', aliases=['seq', 'termos'])
    async def sequencia(self, ctx, formula: str, inicio: int = 1, fim: int = 10):
        """Gera os termos de uma sequência.

        Uso:
          .sequencia <fórmula em n> <início> <fim>

        Exemplos:
          .sequencia n**2 1 10
          .sequencia 2**n 0 8
          .sequencia n*(n+1)/2 1 10
        """
        if fim - inicio > 30:
            return await ctx.send('❌ Máximo de 30 termos por vez.')
        try:
            expr = parse_expressao(formula)
            termos = []
            for i in range(inicio, fim + 1):
                val = expr.subs(n, i)
                termos.append(f'a({i}) = {sp.simplify(val)}')

            embed = discord.Embed(title='📈 Sequência', color=0x00B0F4)
            embed.add_field(name='Fórmula', value=f'```a(n) = {formatar_resultado(expr)}```', inline=False)
            embed.add_field(name=f'Termos (n = {inicio} a {fim})', value=f'```{chr(10).join(termos)}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── SOMA / PRODUTO ──────────────────────────────────────────────────────

    @commands.command(name='soma', aliases=['somatório', 'somatorio'])
    async def soma(self, ctx, formula: str, inicio: int, fim: int):
        """Calcula o somatório de uma expressão.

        Uso:
          .soma <fórmula em n> <início> <fim>

        Exemplos:
          .soma n 1 100
          .soma n**2 1 10
          .soma 1/n**2 1 oo
        """
        try:
            expr = parse_expressao(formula)
            inicio_sp = parse_expressao(str(inicio))

            if str(fim) in ('oo', 'inf', 'infinito'):
                fim_sp = sp.oo
            else:
                fim_sp = parse_expressao(str(fim))

            resultado = sp.summation(expr, (n, inicio_sp, fim_sp))
            resultado_simpl = sp.simplify(resultado)

            embed = discord.Embed(title='Σ Somatório', color=0xFF5733)
            embed.add_field(name='Expressão', value=f'```Σ({formatar_resultado(expr)}), n = {inicio} a {fim}```', inline=False)
            embed.add_field(name='Resultado', value=f'```{formatar_resultado(resultado_simpl)}```', inline=False)
            if resultado_simpl.is_number:
                embed.add_field(name='Valor', value=f'```= {float(resultado_simpl.evalf()):.10g}```', inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')

    # ─── CONVERSÃO ───────────────────────────────────────────────────────────

    @commands.command(name='converter', aliases=['conv'])
    async def converter(self, ctx, valor: str, origem: str, *, destino: str):
        """Converte unidades ou bases numéricas.

        Tipos disponíveis:
          Bases: bin, oct, hex, dec
          Ângulos: graus, radianos

        Exemplos:
          .converter 255 dec hex
          .converter 1010 bin dec
          .converter 180 graus radianos
          .converter 3.14159 radianos graus
        """
        bases = {'bin': 2, 'oct': 8, 'dec': 10, 'hex': 16}
        origem_l = origem.lower()
        destino_l = destino.lower()

        embed = discord.Embed(title='🔄 Conversor', color=0x3498DB)

        try:
            if origem_l in bases and destino_l in bases:
                num = int(valor, bases[origem_l])
                if destino_l == 'bin':
                    resultado = bin(num)
                elif destino_l == 'oct':
                    resultado = oct(num)
                elif destino_l == 'hex':
                    resultado = hex(num)
                else:
                    resultado = str(num)

                embed.add_field(name=f'{valor} ({origem.upper()})', value=f'**{resultado} ({destino.upper()})**', inline=False)

            elif origem_l in ('graus', 'degrees', 'deg') and destino_l in ('radianos', 'radians', 'rad'):
                v = float(valor)
                resultado = v * sp.pi / 180
                embed.add_field(name=f'{v}°', value=f'**{sp.simplify(resultado)} rad ≈ {float(resultado.evalf()):.6f} rad**', inline=False)

            elif origem_l in ('radianos', 'radians', 'rad') and destino_l in ('graus', 'degrees', 'deg'):
                v = parse_expressao(valor)
                resultado = float(v.evalf()) * 180 / sp.pi
                embed.add_field(name=f'{valor} rad', value=f'**{float(resultado.evalf()):.6f}°**', inline=False)

            else:
                return await ctx.send(f'❌ Conversão não suportada: `{origem}` → `{destino}`\nTente: bin, oct, dec, hex, graus, radianos.')

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro: `{e}`')


async def setup(bot):
    await bot.add_cog(Matematica(bot))
