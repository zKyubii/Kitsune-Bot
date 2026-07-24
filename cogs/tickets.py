import datetime

import discord
from discord.ext import commands
from discord import app_commands

import database as db
import logconfig
from cogs.embedbuilder import costruisci_embed

BLU = 0x5865F2
GREEN = 0x2ECC71
RED = 0xE74C3C


# ── CONFIG ────────────────────────────────────────────────────────────────────
def tickets_cfg(config: dict) -> dict:
    return config.setdefault("tickets", {})


def panels(config: dict) -> dict:
    return tickets_cfg(config).get("panels", {})


def multipanels(config: dict) -> dict:
    return tickets_cfg(config).get("multipanels", {})


def new_key(cfg: dict, seq_field: str, prefix: str) -> str:
    n = cfg.get(seq_field, 0) + 1
    cfg[seq_field] = n
    return f"{prefix}{n}"


def _fmt(testo: str, opener, panel_name: str) -> str:
    return (testo or "").replace("{user}", opener.mention).replace("{panel}", panel_name)


def _emoji(raw):
    if not raw:
        return None
    try:
        return discord.PartialEmoji.from_str(str(raw))
    except Exception:
        return None


# ── PERSISTENT: apertura da SELECT ────────────────────────────────────────────
class TicketSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(custom_id="ticket:open:select",
                         placeholder="Select a category!",
                         options=[discord.SelectOption(label="—", value="_")])

    async def callback(self, interaction: discord.Interaction):
        await open_ticket(interaction, self.values[0])


class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ── PERSISTENT: apertura da BOTTONE (panel key dinamica) ──────────────────────
class TicketOpenButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"ticket:open:btn:(?P<panel>[\w-]+)"):
    def __init__(self, panel_key: str, label="Ticket", emoji=None):
        self.panel_key = panel_key
        super().__init__(discord.ui.Button(
            label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
            custom_id=f"ticket:open:btn:{panel_key}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["panel"])

    async def callback(self, interaction: discord.Interaction):
        await open_ticket(interaction, self.panel_key)


# ── PERSISTENT: controlli dentro il ticket (chiudi / reclama) ─────────────────
class TicketControlsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", emoji="🔒",
                       style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket(interaction)

    @discord.ui.button(label="Claim Ticket", emoji="📌",
                       style=discord.ButtonStyle.secondary, custom_id="ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await claim_ticket(interaction)


# ── MODAL: motivo di chiusura ─────────────────────────────────────────────────
class CloseReasonModal(discord.ui.Modal, title="Close ticket"):
    def __init__(self):
        super().__init__()
        self.reason = discord.ui.TextInput(
            label="Close reason", required=True, max_length=300,
            style=discord.TextStyle.paragraph, placeholder="Why are you closing this ticket?")
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await _do_close(interaction, self.reason.value.strip())


# ── APERTURA ──────────────────────────────────────────────────────────────────
async def open_ticket(interaction: discord.Interaction, panel_key: str):
    guild = interaction.guild
    config = db.get_log_config(guild.id)
    if not logconfig.feature_enabled(config, "tickets"):
        return await interaction.response.send_message("🚫 The ticket system is disabled.", ephemeral=True)

    cfg = tickets_cfg(config)
    panel = panels(config).get(panel_key)
    if not panel:
        return await interaction.response.send_message(
            "❌ This category no longer exists.", ephemeral=True)

    member = interaction.user
    # blacklist
    bl = cfg.get("blacklist_roles", [])
    if bl and any(r.id in bl for r in member.roles):
        return await interaction.response.send_message(
            "🚫 You can't open tickets.", ephemeral=True)

    # limiti
    max_user = cfg.get("max_per_user", 0)
    if max_user and db.count_open_tickets(guild.id, member.id) >= max_user:
        return await interaction.response.send_message(
            f"❌ You already have **{max_user}** open ticket(s). Close one first.", ephemeral=True)
    max_tot = cfg.get("max_total", 0)
    if max_tot and db.count_open_tickets(guild.id) >= max_tot:
        return await interaction.response.send_message(
            "❌ The server has reached the maximum number of open tickets. Try again later.",
            ephemeral=True)

    cat_id = panel.get("category") or cfg.get("category")
    categoria = guild.get_channel(cat_id) if cat_id else None
    if categoria is not None and not isinstance(categoria, discord.CategoryChannel):
        categoria = None

    await interaction.response.defer(ephemeral=True)

    # numerazione
    numero = cfg.get("counter", 0) + 1
    if cfg.get("naming", "number") == "username":
        base = "".join(c for c in member.name.lower() if c.isalnum() or c == "-")[:20] or "user"
        nome = f"ticket-{base}"
    else:
        nome = f"ticket-{numero}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                              manage_channels=True, read_message_history=True),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                            read_message_history=True, attach_files=True),
    }
    for rid in panel.get("ping_roles", []):
        role = guild.get_role(rid)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True)

    try:
        canale = await guild.create_text_channel(nome, category=categoria, overwrites=overwrites,
                                                 reason=f"Ticket by {member}")
    except discord.Forbidden:
        return await interaction.followup.send(
            "❌ I can't create the channel (check my permissions / the category).", ephemeral=True)
    except discord.HTTPException as e:
        return await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    cfg["counter"] = numero
    db.save_log_config(guild.id, config)
    db.create_ticket(guild.id, canale.id, panel_key, member.id, numero)

    # messaggio di apertura
    titolo = panel.get("open_title") or "Ticket Opened"
    corpo = _fmt(panel.get("open_body") or "{user} opened a new ticket.", member, panel.get("name", ""))
    embed = discord.Embed(title=titolo, description=corpo, color=BLU)
    embed.set_footer(text=f"Kitsune • {panel.get('name', 'Ticket')}")

    ping = []
    if panel.get("ping_opener", True):
        ping.append(member.mention)
    ping += [f"<@&{r}>" for r in panel.get("ping_roles", [])]
    await canale.send(
        content=" ".join(ping) if ping else None,
        embed=embed, view=TicketControlsView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))

    await interaction.followup.send(f"✅ Ticket created: {canale.mention}", ephemeral=True)


# ── CLAIM (semplice, con toggle) ──────────────────────────────────────────────
async def claim_ticket(interaction: discord.Interaction):
    ticket = db.get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        return await interaction.response.send_message("❌ This isn't a ticket channel.", ephemeral=True)
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message(
            "❌ Only staff can claim tickets.", ephemeral=True)

    if ticket["claimer_id"] is None:
        db.set_ticket_claimer(interaction.channel.id, interaction.user.id)
        await interaction.response.send_message(
            f"📌 Ticket claimed by {interaction.user.mention}.")
    elif ticket["claimer_id"] == interaction.user.id:
        db.set_ticket_claimer(interaction.channel.id, None)
        await interaction.response.send_message(
            f"📌 {interaction.user.mention} released the ticket.")
    else:
        await interaction.response.send_message(
            f"❌ Already claimed by <@{ticket['claimer_id']}>.", ephemeral=True)


# ── CHIUSURA ──────────────────────────────────────────────────────────────────
async def close_ticket(interaction: discord.Interaction):
    ticket = db.get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        return await interaction.response.send_message("❌ This isn't a ticket channel.", ephemeral=True)

    config = db.get_log_config(interaction.guild.id)
    cfg = tickets_cfg(config)
    member = interaction.user
    is_opener = member.id == ticket["opener_id"]
    if is_opener and not cfg.get("opener_can_close", True):
        return await interaction.response.send_message(
            "❌ You can't close your own ticket. A staff member will.", ephemeral=True)
    if not is_opener and not member.guild_permissions.manage_channels:
        return await interaction.response.send_message(
            "❌ You don't have permission to close this ticket.", ephemeral=True)

    if cfg.get("close_reason", False):
        return await interaction.response.send_modal(CloseReasonModal())
    await _do_close(interaction, None)


async def _do_close(interaction: discord.Interaction, reason):
    canale = interaction.channel
    guild = interaction.guild
    ticket = db.get_ticket_by_channel(canale.id)
    if not ticket:
        return
    config = db.get_log_config(guild.id)
    cfg = tickets_cfg(config)

    await interaction.response.send_message("🔒 Closing the ticket...", ephemeral=True)

    # conteggio messaggi per persona
    conteggio = {}
    try:
        async for msg in canale.history(limit=2000):
            if msg.author.bot:
                continue
            conteggio[msg.author.id] = conteggio.get(msg.author.id, 0) + 1
    except discord.HTTPException:
        pass

    opener = guild.get_member(ticket["opener_id"])
    apertura = datetime.datetime.fromisoformat(ticket["created_at"])
    log_ch = guild.get_channel(cfg.get("log_channel")) if cfg.get("log_channel") else None

    if log_ch:
        e = discord.Embed(title="🔒 Ticket Closed", color=RED)
        e.add_field(name="Ticket", value=f"`{canale.name}`", inline=True)
        e.add_field(name="Opened by", value=opener.mention if opener else f"<@{ticket['opener_id']}>", inline=True)
        e.add_field(name="Closed by", value=interaction.user.mention, inline=True)
        e.add_field(name="Opened", value=discord.utils.format_dt(apertura, "f"), inline=True)
        e.add_field(name="Closed", value=discord.utils.format_dt(discord.utils.utcnow(), "f"), inline=True)
        if reason:
            e.add_field(name="Close reason", value=reason[:1024], inline=False)
        if conteggio:
            righe = "\n".join(f"`[ {n} ]` — <@{uid}>"
                              for uid, n in sorted(conteggio.items(), key=lambda x: -x[1]))
            e.add_field(name="Message count", value=righe[:1024], inline=False)
        try:
            await log_ch.send(embed=e)
        except discord.HTTPException:
            pass

    db.close_ticket(canale.id)
    try:
        await canale.delete(reason=f"Ticket closed by {interaction.user}")
    except discord.HTTPException:
        pass


# ── PUBBLICAZIONE MULTIPANEL ──────────────────────────────────────────────────
async def publish_multipanel(guild, config, mp_key: str, canale) -> str:
    """Pubblica il messaggio del multipanel. Ritorna un messaggio d'esito."""
    cfg = tickets_cfg(config)
    mp = multipanels(config).get(mp_key)
    if not mp:
        return "❌ Multipanel not found."
    scelti = [k for k in mp.get("panels", []) if k in panels(config)]
    if not scelti:
        return "❌ Add at least one category to this multipanel first."

    data = db.get_embed(guild.id, mp["embed"]) if mp.get("embed") else None
    embed = costruisci_embed(data, guild=guild) if data else \
        discord.Embed(title="🎫 Tickets", description="Select a category below.", color=BLU)

    view = discord.ui.View(timeout=None)
    if mp.get("style") == "buttons":
        for k in scelti[:25]:
            p = panels(config)[k]
            view.add_item(TicketOpenButton(k, label=p.get("name", "Ticket")[:80],
                                           emoji=_emoji(p.get("emoji"))))
    else:
        sel = TicketSelect()
        sel.options = [
            discord.SelectOption(label=panels(config)[k].get("name", k)[:100], value=k,
                                 description=(panels(config)[k].get("description") or None),
                                 emoji=_emoji(panels(config)[k].get("emoji")))
            for k in scelti[:25]
        ]
        view.add_item(sel)

    try:
        msg = await canale.send(embed=embed, view=view)
    except discord.Forbidden:
        return "❌ I can't write in that channel."
    except discord.HTTPException as e:
        return f"❌ Error: {e}"

    mp["channel_id"] = canale.id
    mp["message_id"] = msg.id
    db.save_log_config(guild.id, config)
    return f"✅ Panel published in {canale.mention}!"


# ── COG ──────────────────────────────────────────────────────────────────────
class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_dynamic_items(TicketOpenButton)
        self.bot.add_view(TicketSelectView())
        self.bot.add_view(TicketControlsView())


async def setup(bot):
    await bot.add_cog(Tickets(bot))
