import discord
from discord.ext import commands
from discord import app_commands

import database as db
import logconfig
from locales import t

BLU = 0x5865F2

# ── EMOJI del messaggio ──────────────────────────────────────────────────────
# Cambiale con le custom quando le hai: basta mettere "<:nome:123456789>" al
# posto dell'unicode, il resto del codice non cambia.
EMOJI = {
    "pex": "✅",       # promozione
    "depex": "❌",     # retrocessione
    "up": "🔺",        # freccia PEX
    "down": "🔻",      # freccia DEPEX
    "reason": "❓",    # motivazione
}


def staff_cfg(config: dict) -> dict:
    return config.setdefault("staff", {})


def staff_allowed(config: dict, member) -> bool:
    """Chi può usare il comando.

    Requisito fisso: **Gestisci ruoli** (senza, il bot non potrebbe applicare
    i ruoli). In più: admin sempre; altrimenti serve uno dei ruoli abilitati
    scelti in dashboard (se non ne è stato scelto nessuno, solo gli admin).
    """
    perms = getattr(member, "guild_permissions", None)
    if not perms or not perms.manage_roles:
        return False
    if perms.administrator:
        return True
    consentiti = config.get("staff", {}).get("allowed_roles", [])
    if not consentiti:
        return False
    return any(r.id in consentiti for r in getattr(member, "roles", []))


def _pos(guild, role_id) -> int:
    r = guild.get_role(role_id) if role_id else None
    return r.position if r else -1


def current_rank(guild, member, cfg):
    """Il ruolo 'ladder' più alto che il membro ha già, o None."""
    ladder = cfg.get("ladder_roles", [])
    posseduti = [r for r in member.roles if r.id in ladder]
    return max(posseduti, key=lambda r: r.position, default=None)


def compute_changes(guild, member, cfg, target_role):
    """Calcola cosa cambia impostando `target_role` come nuovo grado.

    Modello 'set-rank': si toglie tutto ciò che il sistema controlla e si mette
    il target + gli auto-ruoli che superano la loro soglia.
    Ritorna (to_add, to_remove, from_role, direction).
    """
    ladder = set(cfg.get("ladder_roles", []))
    member_role_id = cfg.get("member_role")
    autos = cfg.get("auto_roles", [])

    from_role = current_rank(guild, member, cfg)
    from_pos = from_role.position if from_role else _pos(guild, member_role_id)
    target_pos = target_role.position
    direction = "pex" if target_pos >= from_pos else "depex"

    gestiti = set(ladder)
    if member_role_id:
        gestiti.add(member_role_id)
    for a in autos:
        if a.get("role"):
            gestiti.add(a["role"])

    # Ruoli che il membro DEVE avere dopo l'operazione.
    finali = {target_role.id}
    for a in autos:
        rid, thr = a.get("role"), a.get("threshold")
        if rid and thr and target_pos >= _pos(guild, thr):
            finali.add(rid)

    attuali = {r.id for r in member.roles}
    to_add = [guild.get_role(i) for i in finali if i not in attuali]
    to_remove = [guild.get_role(i) for i in gestiti if i in attuali and i not in finali]
    return ([r for r in to_add if r], [r for r in to_remove if r], from_role, direction)


def build_message(guild, cfg, member, from_role, to_role, reason, direction) -> str:
    """Il messaggio pubblicato, nello stile pex/depex."""
    azione = "PEX" if direction == "pex" else "DEPEX"
    freccia = EMOJI["up"] if direction == "pex" else EMOJI["down"]
    member_role = guild.get_role(cfg.get("member_role")) if cfg.get("member_role") else None
    da = from_role.mention if from_role else (member_role.mention if member_role else "Member")
    return (
        f"{EMOJI[direction]} **{azione}** {member.mention}\n"
        f"{freccia} {da} → {to_role.mention}\n"
        f"{EMOJI['reason']} __{reason}__"
    )


# ── MODAL: motivazione ───────────────────────────────────────────────────────
class ReasonModal(discord.ui.Modal):
    def __init__(self, view, config):
        super().__init__(title=t(config, "staff.reason_title"))
        self.parent = view
        self.box = discord.ui.TextInput(
            label=t(config, "staff.reason_label"), required=True, max_length=300,
            style=discord.TextStyle.paragraph, default=view.reason or None,
            placeholder=t(config, "staff.reason_ph"))
        self.add_item(self.box)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent.reason = self.box.value.strip()
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)


# ── VIEW: composizione + anteprima ───────────────────────────────────────────
class PexRoleSelect(discord.ui.RoleSelect):
    def __init__(self, config):
        super().__init__(placeholder=t(config, "staff.role_ph"),
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.target_role = self.values[0]
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PexReasonButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "staff.reason_btn"), emoji="✍️",
                         style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        await interaction.response.send_modal(ReasonModal(self.view, config))


class PexPublishButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "staff.publish"), emoji="✅",
                         style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(interaction.guild_id)
        cfg = staff_cfg(config)

        if v.target_role is None or not v.reason:
            await interaction.response.send_message(t(config, "staff.need_all"), ephemeral=True)
            return

        to_add, to_remove, from_role, direction = compute_changes(
            v.guild, v.member, cfg, v.target_role)
        if not to_add and not to_remove:
            await interaction.response.send_message(t(config, "staff.no_change"), ephemeral=True)
            return

        # Il bot può gestire solo ruoli sotto il suo ruolo più alto.
        me = v.guild.me
        bloccati = [r for r in (to_add + to_remove) if r >= me.top_role]
        if bloccati:
            await interaction.response.send_message(
                t(config, "staff.bot_too_low", role=bloccati[0].mention), ephemeral=True)
            return

        try:
            if to_remove:
                await v.member.remove_roles(*to_remove, reason=f"{direction} by {interaction.user}")
            if to_add:
                await v.member.add_roles(*to_add, reason=f"{direction} by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(t(config, "staff.forbidden"), ephemeral=True)
            return

        canale = v.guild.get_channel(cfg.get("channel")) if cfg.get("channel") else interaction.channel
        testo = build_message(v.guild, cfg, v.member, from_role, v.target_role, v.reason, direction)
        try:
            await canale.send(
                testo,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except discord.HTTPException as e:
            await interaction.response.send_message(
                t(config, "staff.send_error", error=e), ephemeral=True)
            return

        await interaction.response.edit_message(
            content=t(config, "staff.done", channel=canale.mention), embed=None, view=None)


class PexView(discord.ui.View):
    def __init__(self, author_id, guild, member, config):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild = guild
        self.member = member
        self.target_role = None
        self.reason = None
        self.add_item(PexRoleSelect(config))
        self.add_item(PexReasonButton(config))
        self.add_item(PexPublishButton(config))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                t(db.get_log_config(interaction.guild_id), "staff.only_author"), ephemeral=True)
            return False
        return True

    def build_embed(self):
        config = db.get_log_config(self.guild.id)
        cfg = staff_cfg(config)
        e = discord.Embed(title=t(config, "staff.preview_title"), color=BLU)

        if self.target_role:
            to_add, to_remove, from_role, direction = compute_changes(
                self.guild, self.member, cfg, self.target_role)
            reason = self.reason or t(config, "staff.reason_missing")
            e.description = build_message(self.guild, cfg, self.member, from_role,
                                          self.target_role, reason, direction)
        else:
            e.description = t(config, "staff.pick_role")

        ch = self.guild.get_channel(cfg.get("channel")) if cfg.get("channel") else None
        e.add_field(name=t(config, "common.channel"),
                    value=ch.mention if ch else t(config, "staff.channel_current"), inline=False)
        e.set_footer(text=t(config, "staff.preview_footer"))
        return e


# ── COG ──────────────────────────────────────────────────────────────────────
class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pex", description="Promote or demote a staff member (PEX / DEPEX)")
    @app_commands.describe(user="The member to promote or demote")
    @app_commands.guild_only()
    async def pex(self, interaction: discord.Interaction, user: discord.Member):
        config = db.get_log_config(interaction.guild_id)
        if not logconfig.feature_enabled(config, "staff"):
            await interaction.response.send_message(t(config, "staff.disabled"), ephemeral=True)
            return
        if not staff_allowed(config, interaction.user):
            await interaction.response.send_message(t(config, "staff.no_perm"), ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message(t(config, "staff.target_bot"), ephemeral=True)
            return
        v = PexView(interaction.user.id, interaction.guild, user, config)
        await interaction.response.send_message(embed=v.build_embed(), view=v, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Staff(bot))
