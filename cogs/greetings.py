import discord
from discord.ext import commands
from discord import app_commands

import database as db
from cogs.embedbuilder import costruisci_embed, _replace


class Greetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    set_group = app_commands.Group(
        name="set", description="Configura i messaggi automatici",
        default_permissions=discord.Permissions(manage_guild=True),
    )
    test_group = app_commands.Group(
        name="test", description="Prova i messaggi automatici",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    # ── INVIO ─────────────────────────────────────────────────────────────────
    async def _invia(self, guild, tipo, member):
        conf = db.get_log_config(guild.id).get(tipo, {})
        ch = guild.get_channel(conf.get("channel")) if conf.get("channel") else None
        name = conf.get("embed")
        if not ch or not name:
            return False, f"❌ Il messaggio **{tipo}** non è configurato. Usa `/set {tipo}`."
        data = db.get_embed(guild.id, name)
        if data is None:
            return False, f"❌ L'embed `{name}` non esiste più. Riconfigura con `/set {tipo}`."
        msg = conf.get("message")
        content = _replace(msg, member, guild) if msg else member.mention
        try:
            await ch.send(content=content, embed=costruisci_embed(data, member=member, guild=guild),
                          allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))
        except discord.HTTPException as e:
            return False, f"❌ Errore durante l'invio: {e}"
        return True, f"✅ Messaggio inviato in {ch.mention}."

    # ── SET ─────────────────────────────────────────────────────────────────────
    @set_group.command(name="greet", description="Imposta il canale e l'embed di benvenuto")
    @app_commands.describe(canale="Canale dove inviare il benvenuto", embed="Nome dell'embed da usare",
                           messaggio="Testo sopra l'embed (puoi taggare utente/staff e usare emoji)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_greet(self, interaction: discord.Interaction, canale: discord.TextChannel, embed: str,
                        messaggio: str = None):
        if db.get_embed(interaction.guild_id, embed) is None:
            await interaction.response.send_message(
                f"❌ L'embed `{embed}` non esiste. Crealo con `/embed create`.", ephemeral=True)
            return
        config = db.get_log_config(interaction.guild_id)
        config["greet"] = {"channel": canale.id, "embed": embed, "message": messaggio}
        db.save_log_config(interaction.guild_id, config)
        extra = f"\nMessaggio: {messaggio}" if messaggio else ""
        await interaction.response.send_message(
            f"✅ Benvenuto impostato in {canale.mention} con l'embed `{embed}`.{extra}", ephemeral=True)

    @set_group.command(name="boost", description="Imposta il canale e l'embed per i boost")
    @app_commands.describe(canale="Canale dove inviare il messaggio di boost", embed="Nome dell'embed da usare",
                           messaggio="Testo sopra l'embed (puoi taggare utente/staff e usare emoji)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_boost(self, interaction: discord.Interaction, canale: discord.TextChannel, embed: str,
                        messaggio: str = None):
        if db.get_embed(interaction.guild_id, embed) is None:
            await interaction.response.send_message(
                f"❌ L'embed `{embed}` non esiste. Crealo con `/embed create`.", ephemeral=True)
            return
        config = db.get_log_config(interaction.guild_id)
        config["boost"] = {"channel": canale.id, "embed": embed, "message": messaggio}
        db.save_log_config(interaction.guild_id, config)
        extra = f"\nMessaggio: {messaggio}" if messaggio else ""
        await interaction.response.send_message(
            f"✅ Messaggio di boost impostato in {canale.mention} con l'embed `{embed}`.{extra}", ephemeral=True)

    @set_greet.autocomplete("embed")
    @set_boost.autocomplete("embed")
    async def _embed_ac(self, interaction: discord.Interaction, current: str):
        names = db.list_embeds(interaction.guild_id)
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    # ── TEST ────────────────────────────────────────────────────────────────────
    @test_group.command(name="greet", description="Prova il messaggio di benvenuto (con te come esempio)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_greet(self, interaction: discord.Interaction):
        _, msg = await self._invia(interaction.guild, "greet", interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)

    @test_group.command(name="boost", description="Prova il messaggio di boost (con te come esempio)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_boost(self, interaction: discord.Interaction):
        _, msg = await self._invia(interaction.guild, "boost", interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)

    # ── TRIGGER AUTOMATICI ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._invia(member.guild, "greet", member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Boost: premium_since passa da None a una data
        if before.premium_since is None and after.premium_since is not None:
            await self._invia(after.guild, "boost", after)


async def setup(bot):
    await bot.add_cog(Greetings(bot))
