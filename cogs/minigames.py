import discord
from discord.ext import commands
import random

import database as db
import logconfig


class Minigames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.indovina_partite = {}  # canale_id -> {"numero", "tentativi"}

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        if not logconfig.feature_enabled(db.get_log_config(ctx.guild.id), "minigames"):
            await ctx.send("🚫 I minigiochi non sono disponibili al momento su questo server.")
            return False
        return True

    # ── MONETA ──────────────────────────────────────────────────────────────
    @commands.command(name="moneta")
    async def moneta(self, ctx: commands.Context, scelta: str = None):
        nomi = {"testa": "Testa 🪙", "croce": "Croce ❌"}
        if scelta is None or scelta.lower() not in nomi:
            await ctx.send("❌ Scegli **testa** o **croce**. Esempio: `+moneta testa`")
            return
        scelta = scelta.lower()
        risultato = random.choice(["testa", "croce"])
        esito = "🎉 Hai indovinato!" if scelta == risultato else "😅 Hai sbagliato!"
        await ctx.send(
            f"Hai scelto **{nomi[scelta]}**\n"
            f"La moneta è uscita: **{nomi[risultato]}**\n{esito}")

    # ── 8BALL ───────────────────────────────────────────────────────────────
    @commands.command(name="8ball")
    async def ball8(self, ctx: commands.Context, *, domanda: str = None):
        if not domanda:
            await ctx.send("❌ Scrivi una domanda. Esempio: `+8ball mi sposerò?`")
            return
        risposte = [
            "Sì, assolutamente! ✅", "No, decisamente no. ❌", "Forse... 🤔",
            "Le stelle dicono sì. ⭐", "Non ci contare. 🚫", "Tutto indica di sì. 👍",
            "Le prospettive non sono buone. 😬", "Chiedilo di nuovo più tardi. 🔄",
            "È certo! 💯", "I segni puntano al no. 👎",
        ]
        embed = discord.Embed(title="🎱 Palla Magica", color=discord.Color.purple())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="❓ Domanda", value=domanda[:1000], inline=False)
        embed.add_field(name="💬 Risposta", value=random.choice(risposte), inline=False)
        await ctx.send(embed=embed)

    # ── CARTA / FORBICE / SASSO ──────────────────────────────────────────────
    @commands.command(name="rps")
    async def rps(self, ctx: commands.Context, scelta: str = None):
        opzioni = ["sasso", "carta", "forbice"]
        emoji = {"sasso": "🪨", "carta": "📄", "forbice": "✂️"}
        if scelta is None or scelta.lower() not in opzioni:
            await ctx.send("❌ Scegli **sasso**, **carta** o **forbice**. Esempio: `+rps sasso`")
            return
        scelta = scelta.lower()
        bot_scelta = random.choice(opzioni)

        if scelta == bot_scelta:
            risultato, colore = "Pareggio! 🤝", discord.Color.yellow()
        elif ((scelta == "sasso" and bot_scelta == "forbice") or
              (scelta == "carta" and bot_scelta == "sasso") or
              (scelta == "forbice" and bot_scelta == "carta")):
            risultato, colore = "Hai vinto! 🎉", discord.Color.green()
        else:
            risultato, colore = "Hai perso! 😅", discord.Color.red()

        embed = discord.Embed(title="Carta, Forbice, Sasso", color=colore)
        embed.add_field(name="Tu", value=f"{emoji[scelta]} {scelta.capitalize()}", inline=True)
        embed.add_field(name="Bot", value=f"{emoji[bot_scelta]} {bot_scelta.capitalize()}", inline=True)
        embed.add_field(name="Risultato", value=risultato, inline=False)
        await ctx.send(embed=embed)

    # ── INDOVINA IL NUMERO ───────────────────────────────────────────────────
    @commands.command(name="indovina")
    async def indovina(self, ctx: commands.Context):
        if ctx.channel.id in self.indovina_partite:
            await ctx.send("⚠️ C'è già una partita in corso in questo canale! Usa `+tentativo <numero>`.")
            return
        self.indovina_partite[ctx.channel.id] = {"numero": random.randint(1, 100), "tentativi": 0}
        await ctx.send("🎮 Ho pensato un numero tra **1 e 100**! Usa `+tentativo <numero>` per indovinare.")

    @commands.command(name="tentativo")
    async def tentativo(self, ctx: commands.Context, numero: int = None):
        if numero is None:
            await ctx.send("❌ Scrivi un numero. Esempio: `+tentativo 50`")
            return
        partita = self.indovina_partite.get(ctx.channel.id)
        if not partita:
            await ctx.send("❌ Nessuna partita in corso. Usa `+indovina` per iniziarne una.")
            return
        partita["tentativi"] += 1
        segreto = partita["numero"]
        if numero == segreto:
            del self.indovina_partite[ctx.channel.id]
            t = partita["tentativi"]
            await ctx.send(f"🎉 **{ctx.author.display_name}** ha indovinato! Era **{segreto}** "
                           f"in {t} tentativ{'o' if t == 1 else 'i'}!")
        elif numero < segreto:
            await ctx.send(f"📈 **{numero}** è troppo basso! (Tentativo {partita['tentativi']})")
        else:
            await ctx.send(f"📉 **{numero}** è troppo alto! (Tentativo {partita['tentativi']})")


async def setup(bot):
    await bot.add_cog(Minigames(bot))
