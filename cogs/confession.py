import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db
import logconfig

GIALLO = 0xFCD34D   # confessioni
VIOLA = 0x8B5CF6    # risposte


class ConfessionModal(discord.ui.Modal, title="Confessione anonima"):
    testo = discord.ui.TextInput(
        label="La tua confessione",
        style=discord.TextStyle.paragraph,
        placeholder="Scrivi qui... resterà anonima 🤫",
        max_length=1000,
        required=True,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.pubblica_confessione(interaction, self.testo.value)


class ReplyModal(discord.ui.Modal, title="Rispondi alla confessione"):
    testo = discord.ui.TextInput(
        label="La tua risposta",
        style=discord.TextStyle.paragraph,
        placeholder="Scrivi qui... resterà anonima 🤫",
        max_length=1000,
        required=True,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.pubblica_risposta(interaction, self.testo.value)


class ReplyView(discord.ui.View):
    """View persistente con il pulsante Reply sotto ogni confessione/risposta."""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Reply", emoji="💬", style=discord.ButtonStyle.secondary,
                       custom_id="confession:reply")
    async def reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = db.get_log_config(interaction.guild_id)
        if not logconfig.feature_enabled(config, "confession"):
            await interaction.response.send_message("🚫 Le confessioni sono disattivate.", ephemeral=True)
            return
        await interaction.response.send_modal(ReplyModal(self.cog))


class Confession(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    gruppo = app_commands.Group(name="confession", description="Sistema di confessioni anonime")

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, logconfig.FeatureDisabled):
            msg = "🚫 Le confessioni sono disattivate su questo server."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "⛔ Non hai il permesso necessario per questo comando."
        else:
            msg = f"❌ Errore: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── WRITE ───────────────────────────────────────────────────────────────
    @gruppo.command(name="write", description="Scrivi una confessione anonima")
    @logconfig.feature_check("confession")
    async def write(self, interaction: discord.Interaction):
        config = db.get_config(interaction.guild_id)
        if not config or not config["confession_channel"]:
            await interaction.response.send_message(
                "❌ Le confessioni non sono configurate. Un admin deve impostarle da `/dashboard` → 🔧 Funzioni → Confession.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ConfessionModal(self))

    # ── LOG STAFF ─────────────────────────────────────────────────────────────
    async def _log(self, guild, numero, testo, autore, tipo):
        config = db.get_config(guild.id)
        if not config or not config["log_channel"]:
            return
        log_ch = guild.get_channel(config["log_channel"])
        if not log_ch:
            return
        embed = discord.Embed(
            title=f"🕵️ Log {tipo} #{numero}",
            description=testo,
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Autore", value=f"{autore.mention} (`{autore.id}`)")
        embed.set_thumbnail(url=autore.display_avatar.url)
        try:
            await log_ch.send(embed=embed)
        except discord.HTTPException:
            pass

    # ── CONFESSIONE ─────────────────────────────────────────────────────────────
    async def pubblica_confessione(self, interaction: discord.Interaction, testo: str):
        guild = interaction.guild
        config = db.get_config(guild.id)
        canale = guild.get_channel(config["confession_channel"]) if config else None
        if canale is None:
            await interaction.response.send_message(
                "❌ Il canale delle confessioni non esiste più.", ephemeral=True)
            return

        numero = db.next_confession_number(guild.id)
        embed = discord.Embed(
            title=f"Anonymous Confession (#{numero})",
            description=f'"{testo}"',
            color=GIALLO,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        msg = await canale.send(embed=embed, view=ReplyView(self))
        try:
            await msg.create_thread(name=f"Confession Replies (#{numero})")
        except discord.HTTPException:
            pass

        db.save_confession(guild.id, numero, interaction.user.id, msg.id, testo, None)
        await self._log(guild, numero, testo, interaction.user, "confessione")
        await interaction.response.send_message(
            f"✅ La tua confessione **#{numero}** è stata pubblicata in {canale.mention}!", ephemeral=True)

    # ── RISPOSTA ────────────────────────────────────────────────────────────────
    async def pubblica_risposta(self, interaction: discord.Interaction, testo: str):
        # Trova il thread dove pubblicare
        ch = interaction.channel
        if isinstance(ch, discord.Thread):
            thread = ch
        elif interaction.message and interaction.message.thread:
            thread = interaction.message.thread
        else:
            await interaction.response.send_message(
                "❌ Non riesco a trovare il thread della confessione.", ephemeral=True)
            return

        numero = db.next_confession_number(interaction.guild_id)
        embed = discord.Embed(
            title=f"Anonymous Reply (#{numero})",
            description=f'"{testo}"',
            color=VIOLA,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        await thread.send(embed=embed, view=ReplyView(self))

        db.save_confession(interaction.guild_id, numero, interaction.user.id, 0, testo, None)
        await self._log(interaction.guild, numero, testo, interaction.user, "risposta")
        await interaction.response.send_message("✅ Risposta inviata in anonimo!", ephemeral=True)


async def setup(bot):
    cog = Confession(bot)
    await bot.add_cog(cog)
    bot.add_view(ReplyView(cog))
