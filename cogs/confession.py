import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db
from locales import t


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    """Scorciatoia: risolve la lingua del server da ctx o interaction."""
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)

import logconfig

GIALLO = 0xFCD34D


class ConfessionModal(discord.ui.Modal):
    def __init__(self, cog, config=None):
        # Il campo si costruisce qui (non a livello di classe) così etichetta e
        # placeholder possono seguire la lingua del server.
        super().__init__(title=t(config, "conf.modal_title"))
        self.cog = cog
        self.testo = discord.ui.TextInput(
            label=t(config, "conf.modal_label"),
            style=discord.TextStyle.paragraph,
            placeholder=t(config, "conf.placeholder"),
            max_length=1000,
            required=True,
        )
        self.add_item(self.testo)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.pubblica_confessione(interaction, self.testo.value)


class ConfessionPromptView(discord.ui.View):
    """Pulsante persistente sotto le confessioni per inviarne una nuova."""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Invia una confessione!", emoji="🤫",
                       style=discord.ButtonStyle.secondary, custom_id="confession:new")
    async def nuova(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = db.get_log_config(interaction.guild_id)
        if not logconfig.feature_enabled(config, "confession"):
            await interaction.response.send_message(_t(interaction, "conf.disabled_short"), ephemeral=True)
            return
        cfg = db.get_config(interaction.guild_id)
        if not cfg or not cfg["confession_channel"]:
            await interaction.response.send_message(_t(interaction, "conf.not_configured"), ephemeral=True)
            return
        await interaction.response.send_modal(ConfessionModal(self.cog, db.get_log_config(interaction.guild_id)))


class Confession(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_msg = {}  # guild_id -> ultimo messaggio confessione (per spostare il pulsante)

    gruppo = app_commands.Group(name="confession", description="Anonymous confession system")

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, logconfig.FeatureDisabled):
            msg = _t(interaction, "conf.disabled")
        elif isinstance(error, app_commands.MissingPermissions):
            msg = _t(interaction, "conf.no_perm")
        else:
            msg = _t(interaction, "mod.error", error=error)
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    @gruppo.command(name="write", description="Write an anonymous confession")
    @logconfig.feature_check("confession")
    async def write(self, interaction: discord.Interaction):
        config = db.get_config(interaction.guild_id)
        if not config or not config["confession_channel"]:
            await interaction.response.send_message(
                _t(interaction, "conf.not_configured_admin"),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ConfessionModal(self, db.get_log_config(interaction.guild_id)))

    async def _log(self, guild, numero, testo, autore):
        config = db.get_config(guild.id)
        if not config or not config["log_channel"]:
            return
        log_ch = guild.get_channel(config["log_channel"])
        if not log_ch:
            return
        embed = discord.Embed(
            title=f"🕵️ Log confessione #{numero}",
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

    async def pubblica_confessione(self, interaction: discord.Interaction, testo: str):
        guild = interaction.guild
        config = db.get_config(guild.id)
        canale = guild.get_channel(config["confession_channel"]) if config else None
        if canale is None:
            await interaction.response.send_message(
                _t(interaction, "conf.channel_gone"), ephemeral=True)
            return

        numero = db.next_confession_number(guild.id)
        embed = discord.Embed(
            title=f"🤫 Confessione #{numero}",
            description=testo,
            color=GIALLO,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text="Anonimo")

        # Sposta il pulsante: lo tolgo dalla confessione precedente
        vecchio = self.last_msg.get(guild.id)
        if vecchio:
            try:
                await vecchio.edit(view=None)
            except (discord.HTTPException, discord.NotFound):
                pass

        msg = await canale.send(embed=embed, view=ConfessionPromptView(self))
        self.last_msg[guild.id] = msg

        db.save_confession(guild.id, numero, interaction.user.id, msg.id, testo, None)
        await self._log(guild, numero, testo, interaction.user)
        await interaction.response.send_message(
            _t(interaction, "conf.published", n=numero, channel=canale.mention), ephemeral=True)


async def setup(bot):
    cog = Confession(bot)
    await bot.add_cog(cog)
    bot.add_view(ConfessionPromptView(cog))
