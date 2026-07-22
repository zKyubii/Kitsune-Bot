import random

import discord
from discord.ext import commands

import database as db
import logconfig
from locales import t


def _t(ctx, key: str, **kwargs) -> str:
    return t(db.get_log_config(ctx.guild.id), key, **kwargs)


# Le scelte si accettano sia in italiano sia in inglese: la chiave interna
# resta l'italiano, l'etichetta mostrata la decide la lingua del server.
COIN_ALIAS = {"testa": "testa", "heads": "testa", "croce": "croce", "tails": "croce"}
COIN_LABEL = {"testa": "mg.coin_heads", "croce": "mg.coin_tails"}

RPS_ALIAS = {"sasso": "sasso", "rock": "sasso",
             "carta": "carta", "paper": "carta",
             "forbice": "forbice", "scissors": "forbice"}
RPS_LABEL = {"sasso": "mg.rps_rock", "carta": "mg.rps_paper", "forbice": "mg.rps_scissors"}
RPS_EMOJI = {"sasso": "🪨", "carta": "📄", "forbice": "✂️"}


class Minigames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.indovina_partite = {}

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        if not logconfig.feature_enabled(db.get_log_config(ctx.guild.id), "minigames"):
            await ctx.send(_t(ctx, "mg.disabled"))
            return False
        return True

    # ── MONETA ──────────────────────────────────────────────────────────────
    @commands.command(name="moneta")
    async def moneta(self, ctx: commands.Context, scelta: str = None):
        chiave = COIN_ALIAS.get((scelta or "").lower())
        if chiave is None:
            await ctx.send(_t(ctx, "mg.coin_usage"))
            return
        risultato = random.choice(["testa", "croce"])
        esito = _t(ctx, "mg.coin_win" if chiave == risultato else "mg.coin_lose")
        await ctx.send(_t(ctx, "mg.coin_result",
                          choice=_t(ctx, COIN_LABEL[chiave]),
                          result=_t(ctx, COIN_LABEL[risultato]),
                          outcome=esito))

    # ── 8BALL ───────────────────────────────────────────────────────────────
    @commands.command(name="8ball")
    async def ball8(self, ctx: commands.Context, *, domanda: str = None):
        if not domanda:
            await ctx.send(_t(ctx, "mg.8ball_usage"))
            return
        risposte = _t(ctx, "mg.8ball_answers").split("\n")
        embed = discord.Embed(title=_t(ctx, "mg.8ball_title"), color=discord.Color.purple())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name=_t(ctx, "mg.8ball_question"), value=domanda[:1000], inline=False)
        embed.add_field(name=_t(ctx, "mg.8ball_answer"), value=random.choice(risposte), inline=False)
        await ctx.send(embed=embed)

    # ── CARTA / FORBICE / SASSO ──────────────────────────────────────────────
    @commands.command(name="rps")
    async def rps(self, ctx: commands.Context, scelta: str = None):
        chiave = RPS_ALIAS.get((scelta or "").lower())
        if chiave is None:
            await ctx.send(_t(ctx, "mg.rps_usage"))
            return
        bot_scelta = random.choice(["sasso", "carta", "forbice"])

        if chiave == bot_scelta:
            risultato, colore = _t(ctx, "mg.rps_draw"), discord.Color.yellow()
        elif ((chiave == "sasso" and bot_scelta == "forbice") or
              (chiave == "carta" and bot_scelta == "sasso") or
              (chiave == "forbice" and bot_scelta == "carta")):
            risultato, colore = _t(ctx, "mg.rps_win"), discord.Color.green()
        else:
            risultato, colore = _t(ctx, "mg.rps_lose"), discord.Color.red()

        embed = discord.Embed(title=_t(ctx, "mg.rps_title"), color=colore)
        embed.add_field(name=_t(ctx, "mg.rps_you"),
                        value=f"{RPS_EMOJI[chiave]} {_t(ctx, RPS_LABEL[chiave])}", inline=True)
        embed.add_field(name=_t(ctx, "mg.rps_bot"),
                        value=f"{RPS_EMOJI[bot_scelta]} {_t(ctx, RPS_LABEL[bot_scelta])}", inline=True)
        embed.add_field(name=_t(ctx, "mg.rps_result"), value=risultato, inline=False)
        await ctx.send(embed=embed)

    # ── INDOVINA IL NUMERO ───────────────────────────────────────────────────
    @commands.command(name="indovina")
    async def indovina(self, ctx: commands.Context):
        if ctx.channel.id in self.indovina_partite:
            await ctx.send(_t(ctx, "mg.guess_running"))
            return
        self.indovina_partite[ctx.channel.id] = {"numero": random.randint(1, 100), "tentativi": 0}
        await ctx.send(_t(ctx, "mg.guess_started"))

    @commands.command(name="tentativo")
    async def tentativo(self, ctx: commands.Context, numero: int = None):
        if numero is None:
            await ctx.send(_t(ctx, "mg.guess_need_number"))
            return
        partita = self.indovina_partite.get(ctx.channel.id)
        if not partita:
            await ctx.send(_t(ctx, "mg.guess_no_game"))
            return
        partita["tentativi"] += 1
        segreto = partita["numero"]
        tentativi = partita["tentativi"]
        if numero == segreto:
            del self.indovina_partite[ctx.channel.id]
            chiave = "mg.guess_won_one" if tentativi == 1 else "mg.guess_won_many"
            await ctx.send(_t(ctx, chiave, user=ctx.author.display_name,
                              number=segreto, tries=tentativi))
        elif numero < segreto:
            await ctx.send(_t(ctx, "mg.guess_low", number=numero, tries=tentativi))
        else:
            await ctx.send(_t(ctx, "mg.guess_high", number=numero, tries=tentativi))


async def setup(bot):
    await bot.add_cog(Minigames(bot))
