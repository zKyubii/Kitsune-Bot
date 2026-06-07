import discord
from discord.ext import commands
from discord import app_commands
import random

import logconfig

class Minigames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.indovina_partite = {}  # Tiene traccia delle partite attive per canale

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, logconfig.FeatureDisabled):
            msg = "🚫 I minigiochi sono disattivati su questo server."
        else:
            msg = f"❌ Errore: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── DADO ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="dado", description="Lancia un dado (default: 6 facce)")
    @logconfig.feature_check("minigames")
    async def dado(self, interaction: discord.Interaction, facce: int = 6):
        if facce < 2:
            await interaction.response.send_message("❌ Il dado deve avere almeno 2 facce.", ephemeral=True)
            return
        risultato = random.randint(1, facce)
        await interaction.response.send_message(f"🎲 Hai lanciato un **d{facce}**: **{risultato}**")

    # ── MONETA ────────────────────────────────────────────────────────────────
    @app_commands.command(name="moneta", description="Lancia una moneta")
    @logconfig.feature_check("minigames")
    async def moneta(self, interaction: discord.Interaction):
        risultato = random.choice(["Testa 🪙", "Croce ❌"])
        await interaction.response.send_message(f"La moneta è uscita: **{risultato}**!")

    # ── 8BALL ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="8ball", description="Chiedi qualcosa alla palla magica")
    @logconfig.feature_check("minigames")
    async def ball8(self, interaction: discord.Interaction, domanda: str):
        risposte = [
            "Sì, assolutamente! ✅",
            "No, decisamente no. ❌",
            "Forse... 🤔",
            "Le stelle dicono sì. ⭐",
            "Non ci contare. 🚫",
            "Tutto indica di sì. 👍",
            "Le prospettive non sono buone. 😬",
            "Chiedilo di nuovo più tardi. 🔄",
            "È certo! 💯",
            "I segni puntano al no. 👎",
        ]
        risposta = random.choice(risposte)
        embed = discord.Embed(color=discord.Color.purple())
        embed.add_field(name="❓ Domanda", value=domanda, inline=False)
        embed.add_field(name="🎱 Risposta", value=risposta, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── CARTA FORBICE SASSO ───────────────────────────────────────────────────
    @app_commands.command(name="rps", description="Gioca a carta, forbice, sasso contro il bot")
    @app_commands.choices(scelta=[
        app_commands.Choice(name="🪨 Sasso", value="sasso"),
        app_commands.Choice(name="📄 Carta", value="carta"),
        app_commands.Choice(name="✂️ Forbice", value="forbice"),
    ])
    @logconfig.feature_check("minigames")
    async def rps(self, interaction: discord.Interaction, scelta: app_commands.Choice[str]):
        opzioni = ["sasso", "carta", "forbice"]
        bot_scelta = random.choice(opzioni)
        emoji = {"sasso": "🪨", "carta": "📄", "forbice": "✂️"}

        if scelta.value == bot_scelta:
            risultato = "Pareggio! 🤝"
            colore = discord.Color.yellow()
        elif (
            (scelta.value == "sasso" and bot_scelta == "forbice") or
            (scelta.value == "carta" and bot_scelta == "sasso") or
            (scelta.value == "forbice" and bot_scelta == "carta")
        ):
            risultato = "Hai vinto! 🎉"
            colore = discord.Color.green()
        else:
            risultato = "Hai perso! 😅"
            colore = discord.Color.red()

        embed = discord.Embed(title="Carta, Forbice, Sasso", color=colore)
        embed.add_field(name="Tu", value=f"{emoji[scelta.value]} {scelta.value.capitalize()}", inline=True)
        embed.add_field(name="Bot", value=f"{emoji[bot_scelta]} {bot_scelta.capitalize()}", inline=True)
        embed.add_field(name="Risultato", value=risultato, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── INDOVINA IL NUMERO ────────────────────────────────────────────────────
    @app_commands.command(name="indovina", description="Inizia una partita a indovina il numero (1-100)")
    @logconfig.feature_check("minigames")
    async def indovina(self, interaction: discord.Interaction):
        canale_id = interaction.channel_id
        if canale_id in self.indovina_partite:
            await interaction.response.send_message("⚠️ C'è già una partita in corso in questo canale! Usa `/tentativo`.", ephemeral=True)
            return
        numero = random.randint(1, 100)
        self.indovina_partite[canale_id] = {"numero": numero, "tentativi": 0}
        await interaction.response.send_message("🎮 Ho pensato un numero tra **1 e 100**! Usa `/tentativo <numero>` per indovinare.")

    @app_commands.command(name="tentativo", description="Fai un tentativo per indovinare il numero")
    @logconfig.feature_check("minigames")
    async def tentativo(self, interaction: discord.Interaction, numero: int):
        canale_id = interaction.channel_id
        if canale_id not in self.indovina_partite:
            await interaction.response.send_message("❌ Nessuna partita in corso. Usa `/indovina` per iniziarne una.", ephemeral=True)
            return
        partita = self.indovina_partite[canale_id]
        partita["tentativi"] += 1
        segreto = partita["numero"]

        if numero == segreto:
            del self.indovina_partite[canale_id]
            await interaction.response.send_message(f"🎉 **{interaction.user.display_name}** ha indovinato! Era **{segreto}** in {partita['tentativi']} tentativ{'o' if partita['tentativi'] == 1 else 'i'}!")
        elif numero < segreto:
            await interaction.response.send_message(f"📈 **{numero}** è troppo basso! (Tentativo {partita['tentativi']})")
        else:
            await interaction.response.send_message(f"📉 **{numero}** è troppo alto! (Tentativo {partita['tentativi']})")

async def setup(bot):
    await bot.add_cog(Minigames(bot))
