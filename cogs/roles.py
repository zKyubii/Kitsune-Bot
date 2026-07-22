import discord
from discord.ext import commands
from discord import app_commands

import database as db
from locales import t


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    """Scorciatoia: risolve la lingua del server da ctx o interaction."""
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)



def _puo_assegnare(interaction: discord.Interaction, ruolo: discord.Role):
    """Controlla se il ruolo è assegnabile da moderatore e bot. Ritorna messaggio d'errore o None."""
    guild = interaction.guild
    if ruolo.is_default():
        return _t(interaction, "roles.everyone")
    if ruolo.managed:
        return _t(interaction, "roles.managed")
    if ruolo >= guild.me.top_role:
        return _t(interaction, "roles.bot_too_low")
    if interaction.user.id != guild.owner_id and ruolo >= interaction.user.top_role:
        return _t(interaction, "roles.higher")
    return None


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    gruppo = app_commands.Group(
        name="role",
        description="Gestione dei ruoli",
        default_permissions=discord.Permissions(manage_roles=True),
    )

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            msg = _t(interaction, "roles.need_perm")
        else:
            msg = _t(interaction, "mod.error", error=error)
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── ADD ─────────────────────────────────────────────────────────────────────
    @gruppo.command(name="add", description="Aggiunge un ruolo a un utente")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add(self, interaction: discord.Interaction, utente: discord.Member, ruolo: discord.Role):
        err = _puo_assegnare(interaction, ruolo)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if ruolo in utente.roles:
            await interaction.response.send_message(_t(interaction, "roles.already_has", user=utente.mention, role=ruolo.mention), ephemeral=True)
            return
        await utente.add_roles(ruolo, reason=f"/role add da {interaction.user}")
        await interaction.response.send_message(_t(interaction, "roles.added", role=ruolo.mention, user=utente.mention))

    # ── REMOVE ──────────────────────────────────────────────────────────────────
    @gruppo.command(name="remove", description="Rimuove un ruolo a un utente")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove(self, interaction: discord.Interaction, utente: discord.Member, ruolo: discord.Role):
        err = _puo_assegnare(interaction, ruolo)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if ruolo not in utente.roles:
            await interaction.response.send_message(_t(interaction, "roles.doesnt_have", user=utente.mention, role=ruolo.mention), ephemeral=True)
            return
        await utente.remove_roles(ruolo, reason=f"/role remove da {interaction.user}")
        await interaction.response.send_message(_t(interaction, "roles.removed", role=ruolo.mention, user=utente.mention))

    # ── OPERAZIONI DI MASSA ─────────────────────────────────────────────────────
    async def _massa(self, interaction, ruolo, azione, filtro, descr):
        err = _puo_assegnare(interaction, ruolo)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        await interaction.response.defer()
        val = azione.value if azione else "add"
        count = 0
        for m in interaction.guild.members:
            if not filtro(m):
                continue
            ha = ruolo in m.roles
            try:
                if val == "add" and not ha:
                    await m.add_roles(ruolo, reason=f"/role {descr} da {interaction.user}")
                    count += 1
                elif val == "remove" and ha:
                    await m.remove_roles(ruolo, reason=f"/role {descr} da {interaction.user}")
                    count += 1
            except discord.HTTPException:
                pass

        verbo = "aggiunto a" if val == "add" else "rimosso da"
        await interaction.followup.send(_t(interaction, "roles.mass_done", role=ruolo.mention, verb=verbo, count=count, what=descr))

    _AZIONI = [
        app_commands.Choice(name="Aggiungi", value="add"),
        app_commands.Choice(name="Rimuovi", value="remove"),
    ]

    @gruppo.command(name="all", description="Dà (o toglie) un ruolo a TUTTI i membri")
    @app_commands.choices(azione=_AZIONI)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def all(self, interaction: discord.Interaction, ruolo: discord.Role,
                  azione: app_commands.Choice[str] = None):
        await self._massa(interaction, ruolo, azione, lambda m: True, "membri")

    @gruppo.command(name="humans", description="Dà (o toglie) un ruolo solo agli utenti (no bot)")
    @app_commands.choices(azione=_AZIONI)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def humans(self, interaction: discord.Interaction, ruolo: discord.Role,
                     azione: app_commands.Choice[str] = None):
        await self._massa(interaction, ruolo, azione, lambda m: not m.bot, "utenti")

    @gruppo.command(name="bots", description="Dà (o toglie) un ruolo solo ai bot")
    @app_commands.choices(azione=_AZIONI)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def bots(self, interaction: discord.Interaction, ruolo: discord.Role,
                   azione: app_commands.Choice[str] = None):
        await self._massa(interaction, ruolo, azione, lambda m: m.bot, "bot")

    # ── AUTOROLE ────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ids = db.get_log_config(member.guild.id).get("autoroles", [])
        if not ids:
            return
        ruoli = [member.guild.get_role(r) for r in ids]
        ruoli = [r for r in ruoli if r and not r.managed and r < member.guild.me.top_role]
        if ruoli:
            try:
                await member.add_roles(*ruoli, reason="Autorole")
            except discord.HTTPException:
                pass


async def setup(bot):
    await bot.add_cog(Roles(bot))
