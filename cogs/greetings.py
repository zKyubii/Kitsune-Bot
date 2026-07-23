import asyncio
import time

import discord
from discord.ext import commands
from discord import app_commands

import database as db
from locales import t


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    """Scorciatoia: risolve la lingua del server da ctx o interaction."""
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)

from cogs.embedbuilder import costruisci_embed, _replace

_BOOST_MSG_TYPES = (
    discord.MessageType.premium_guild_subscription,
    discord.MessageType.premium_guild_tier_1,
    discord.MessageType.premium_guild_tier_2,
    discord.MessageType.premium_guild_tier_3,
)


class Greetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # user_id -> timestamp dell'ultimo boost annunciato dal messaggio di sistema.
        # Serve solo perché il fallback on_member_update non duplichi lo stesso boost.
        self._boost_da_messaggio = {}

    set_group = app_commands.Group(
        name="set", description="Configure the automatic messages",
        default_permissions=discord.Permissions(manage_guild=True),
    )
    test_group = app_commands.Group(
        name="test", description="Test the automatic messages",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    # ── INVIO ─────────────────────────────────────────────────────────────────
    async def _invia(self, guild, tipo, member):
        conf = db.get_log_config(guild.id).get(tipo, {})
        ch = guild.get_channel(conf.get("channel")) if conf.get("channel") else None
        name = conf.get("embed")
        if not ch or not name:
            return False, t(db.get_log_config(guild.id), "greet.not_configured", type=tipo)
        data = db.get_embed(guild.id, name)
        if data is None:
            return False, t(db.get_log_config(guild.id), "greet.embed_gone", name=name, type=tipo)
        msg = conf.get("message")
        content = _replace(msg, member, guild) if msg else member.mention
        try:
            await ch.send(content=content, embed=costruisci_embed(data, member=member, guild=guild),
                          allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))
        except discord.HTTPException as e:
            return False, t(db.get_log_config(guild.id), "greet.send_error", error=e)
        return True, t(db.get_log_config(guild.id), "greet.sent", channel=ch.mention)

    # ── SET ─────────────────────────────────────────────────────────────────────
    @set_group.command(name="greet", description="Set the welcome channel and embed")
    @app_commands.describe(canale="Channel to send the welcome in", embed="Name of the embed to use",
                           messaggio="Text above the embed (you can tag users/staff and use emoji)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.rename(canale="channel", messaggio="message")
    async def set_greet(self, interaction: discord.Interaction, canale: discord.TextChannel, embed: str,
                        messaggio: str = None):
        if db.get_embed(interaction.guild_id, embed) is None:
            await interaction.response.send_message(
                _t(interaction, "greet.embed_missing", name=embed), ephemeral=True)
            return
        config = db.get_log_config(interaction.guild_id)
        config["greet"] = {"channel": canale.id, "embed": embed, "message": messaggio}
        db.save_log_config(interaction.guild_id, config)
        extra = f"\nMessage: {messaggio}" if messaggio else ""
        await interaction.response.send_message(
            _t(interaction, "greet.welcome_set", channel=canale.mention, name=embed, extra=extra), ephemeral=True)

    @set_group.command(name="boost", description="Set the boost channel and embed")
    @app_commands.describe(canale="Channel to send the boost message in", embed="Name of the embed to use",
                           messaggio="Text above the embed (you can tag users/staff and use emoji)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.rename(canale="channel", messaggio="message")
    async def set_boost(self, interaction: discord.Interaction, canale: discord.TextChannel, embed: str,
                        messaggio: str = None):
        if db.get_embed(interaction.guild_id, embed) is None:
            await interaction.response.send_message(
                _t(interaction, "greet.embed_missing", name=embed), ephemeral=True)
            return
        config = db.get_log_config(interaction.guild_id)
        config["boost"] = {"channel": canale.id, "embed": embed, "message": messaggio}
        db.save_log_config(interaction.guild_id, config)
        extra = f"\nMessage: {messaggio}" if messaggio else ""
        await interaction.response.send_message(
            _t(interaction, "greet.boost_set", channel=canale.mention, name=embed, extra=extra), ephemeral=True)

    @set_greet.autocomplete("embed")
    @set_boost.autocomplete("embed")
    async def _embed_ac(self, interaction: discord.Interaction, current: str):
        names = db.list_embeds(interaction.guild_id)
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    # ── TEST ────────────────────────────────────────────────────────────────────
    @test_group.command(name="greet", description="Test the welcome message (using you as the example)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_greet(self, interaction: discord.Interaction):
        _, msg = await self._invia(interaction.guild, "greet", interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)

    @test_group.command(name="boost", description="Test the boost message (using you as the example)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_boost(self, interaction: discord.Interaction):
        _, msg = await self._invia(interaction.guild, "boost", interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)

    # ── TRIGGER AUTOMATICI ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._invia(member.guild, "greet", member)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Trigger principale dei boost.

        Discord manda UN messaggio di sistema per OGNI boost, quindi due boost
        ravvicinati (o due boost dello stesso utente) producono due embed.
        """
        if not message.guild or message.type not in _BOOST_MSG_TYPES:
            return
        autore = message.author
        if autore is None or autore.bot:
            return
        self._boost_da_messaggio[autore.id] = time.time()
        await self._invia(message.guild, "boost", autore)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Fallback: scatta solo se il messaggio di sistema non è arrivato.

        Serve ai server che hanno disattivato i messaggi di boost nel canale di
        sistema (lì on_message non scatta mai). Nota: `premium_since` passa da
        None a una data solo al PRIMO boost, quindi questo non può gestire i
        boost successivi — per quelli l'unica fonte affidabile è on_message.
        """
        if before.premium_since is not None or after.premium_since is None or after.bot:
            return
        # Diamo tempo al messaggio di sistema di arrivare, poi controlliamo
        # se ha già annunciato lui questo boost.
        await asyncio.sleep(3)
        if time.time() - self._boost_da_messaggio.get(after.id, 0) < 10:
            return
        await self._invia(after.guild, "boost", after)


async def setup(bot):
    await bot.add_cog(Greetings(bot))
