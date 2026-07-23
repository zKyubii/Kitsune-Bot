import re
import json

import discord
from discord.ext import commands
from discord import app_commands

import database as db
from locales import t


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    """Scorciatoia: risolve la lingua del server da ctx o interaction."""
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)

from logconfig import feature_enabled

SEPARATOR = "─────── ☁️ ───────"

_INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/([a-zA-Z0-9-]+)",
    re.IGNORECASE,
)


def can_partner(member: discord.Member, config: dict) -> bool:
    """Vero se il membro può usare /partnership (admin/manage_guild o ruolo abilitato)."""
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    allowed = config.get("partnership", {}).get("roles", [])
    if not allowed:
        return False  # nessun ruolo impostato → solo admin
    return any(r.id in allowed for r in member.roles)


def find_invite(text: str):
    """Estrae il primo invito Discord dal testo, o None."""
    m = _INVITE_RE.search(text or "")
    return m.group(0) if m else None


def decide_ping(partner_member_count: int, ping_cfg: dict) -> str:
    """Sceglie il ping in base ai membri del SERVER PARTNER."""
    count = partner_member_count or 0
    pings = []
    everyone = ping_cfg.get("everyone")
    here = ping_cfg.get("here")
    if everyone and count >= everyone:
        pings.append("@everyone")
    elif here and count >= here:
        pings.append("@here")
    custom_role = ping_cfg.get("custom_role")
    custom_members = ping_cfg.get("custom_members")
    if custom_role and custom_members and count >= custom_members:
        pings.append(f"<@&{custom_role}>")
    return " ".join(pings)


class PartnerModal(discord.ui.Modal, title="Run a Partner!"):
    def __init__(self, manager: discord.Member | None):
        super().__init__()
        self.manager = manager
        self.descrizione = discord.ui.TextInput(
            label="Descrizione", style=discord.TextStyle.paragraph,
            placeholder="https://discord.gg/...", required=True, max_length=2000)
        self.add_item(self.descrizione)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        p = config.get("partnership", {})
        channel = interaction.guild.get_channel(p.get("channel")) if p.get("channel") else None
        if not channel:
            return await interaction.response.send_message(
                _t(interaction, "partner.channel_gone"), ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        descrizione = self.descrizione.value

        # Ping in base ai membri del server partner (letti dall'invito)
        ping_str = ""
        invite_url = find_invite(descrizione)
        if invite_url:
            try:
                inv = await interaction.client.fetch_invite(invite_url, with_counts=True)
                ping_str = decide_ping(inv.approximate_member_count or 0, p.get("ping", {}))
            except discord.HTTPException:
                pass

        manager_txt = self.manager.mention if self.manager else "Manager not specified"
        info = (
            f"{SEPARATOR}\n"
            f"👤 **Author:** {interaction.user.mention}\n"
            f"🚀 **Server:** {interaction.guild.name}\n"
            f"🎛️ **Manager:** {manager_txt}\n"
            f"📣 **Ping:** {ping_str}"
        )

        try:
            # 1° messaggio: la descrizione (l'invito genera l'anteprima sotto).
            #    Niente menzioni qui, così nessuno può abusare con @everyone nel testo.
            msg1 = await channel.send(descrizione, allowed_mentions=discord.AllowedMentions.none())
            # 2° messaggio: il blocco info, con i ping consentiti.
            msg2 = await channel.send(
                info,
                allowed_mentions=discord.AllowedMentions(everyone=True, roles=True, users=True))
        except discord.Forbidden:
            return await interaction.followup.send(
                _t(interaction, "partner.no_write_perm"), ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(_t(interaction, "partner.send_error", error=e), ephemeral=True)

        # Salva la partner per poterla rimuovere se author o manager lasciano il server.
        db.add_partnership(interaction.guild_id, channel.id, [msg1.id, msg2.id],
                           interaction.user.id, self.manager.id if self.manager else None)
        await interaction.followup.send(_t(interaction, "partner.published", channel=channel.mention), ephemeral=True)


class Partnership(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Cancella le partner quando author o manager lasciano il server."""
        rows = db.get_partnerships_by_user(member.guild.id, member.id)
        for row in rows:
            channel = member.guild.get_channel(row["channel_id"])
            if channel:
                for mid in json.loads(row["message_ids"]):
                    try:
                        msg = await channel.fetch_message(mid)
                        await msg.delete()
                    except discord.HTTPException:
                        pass
            db.delete_partnership(row["id"])

    @app_commands.command(name="partnership", description="Run a partnership")
    @app_commands.describe(manager="The user you are doing the partnership with (optional)")
    @app_commands.guild_only()
    async def partnership(self, interaction: discord.Interaction, manager: discord.Member = None):
        config = db.get_log_config(interaction.guild_id)
        if not feature_enabled(config, "partnership"):
            return await interaction.response.send_message(
                _t(interaction, "partner.disabled"), ephemeral=True)
        if not can_partner(interaction.user, config):
            return await interaction.response.send_message(
                _t(interaction, "partner.no_role"), ephemeral=True)
        if not config.get("partnership", {}).get("channel"):
            return await interaction.response.send_message(
                "❌ The partnerships channel isn't configured.\n"
                "Vai su `/dashboard` → **Funzioni** → **Partnership**.", ephemeral=True)
        await interaction.response.send_modal(PartnerModal(manager))


async def setup(bot):
    await bot.add_cog(Partnership(bot))
