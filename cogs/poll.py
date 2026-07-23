import re

import discord
from discord.ext import commands
from discord import app_commands

import database as db
import logconfig
from locales import t

BLU = 0x5865F2
MAX_OPZIONI = 10

# Emoji assegnate alle opzioni che non ne hanno una scritta a mano.
DEFAULT_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

_CUSTOM_EMOJI = re.compile(r"^(<a?:[\w~]+:\d+>)\s*(.*)$")


def _split_emoji(riga: str):
    """Stacca l'emoji iniziale da una riga: '🍖 Carne' → ('🍖', 'Carne').

    Restituisce (None, riga) se la riga non comincia con un'emoji.
    """
    riga = riga.strip()
    m = _CUSTOM_EMOJI.match(riga)
    if m and m.group(2):
        return m.group(1), m.group(2).strip()
    parti = riga.split(None, 1)
    # Primo token senza lettere/cifre = lo trattiamo come emoji unicode.
    if len(parti) == 2 and parti[0] and not re.search(r"[A-Za-z0-9]", parti[0]):
        return parti[0], parti[1].strip()
    return None, riga


def parse_opzioni(testo: str):
    """Una riga = un'opzione. Ritorna [{'emoji': str, 'testo': str}, ...]."""
    opzioni = []
    for riga in (testo or "").splitlines():
        if not riga.strip():
            continue
        emoji, label = _split_emoji(riga)
        if not label:
            continue
        opzioni.append({"emoji": emoji, "testo": label})
        if len(opzioni) >= MAX_OPZIONI:
            break
    # Le opzioni senza emoji ricevono 1️⃣2️⃣3️⃣… saltando quelle già usate a mano
    usate = {o["emoji"] for o in opzioni if o["emoji"]}
    disponibili = [e for e in DEFAULT_EMOJI if e not in usate]
    for o in opzioni:
        if not o["emoji"]:
            o["emoji"] = disponibili.pop(0) if disponibili else "▫️"
    return opzioni


def poll_cfg(config: dict) -> dict:
    return config.setdefault("poll", {})


def poll_allowed(config: dict, member) -> bool:
    """Chi può creare le poll.

    Gli amministratori sempre. Se in dashboard sono stati scelti dei ruoli,
    valgono quelli; se non è stato scelto nessun ruolo, restano solo gli admin.
    """
    if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
        return True
    consentiti = config.get("poll", {}).get("allowed_roles", [])
    if not consentiti:
        return False
    return any(r.id in consentiti for r in getattr(member, "roles", []))


def build_poll_text(titolo: str, domanda: str, opzioni: list, ping_role=None) -> str:
    """Il messaggio della poll: titolo grande, domanda in grassetto, opzioni spaziate.

    `ping_role` (id) finisce in fondo, staccato come le opzioni.
    """
    righe = "\n\n".join(f"{o['emoji']} {o['testo']}" for o in opzioni)
    testo = f"# {titolo}\n**{domanda}**\n\n{righe}"
    if ping_role:
        testo += f"\n\n<@&{ping_role}>"
    return testo


# ── MODAL: titolo + domanda + opzioni ────────────────────────────────────────
class PollModal(discord.ui.Modal):
    def __init__(self, cog, config):
        super().__init__(title=t(config, "poll.modal_title"))
        self.cog = cog
        prossimo = poll_cfg(config).get("counter", 0) + 1

        self.titolo = discord.ui.TextInput(
            label=t(config, "poll.field_title"), required=False, max_length=100,
            placeholder=t(config, "poll.ph_title", n=prossimo))
        self.domanda = discord.ui.TextInput(
            label=t(config, "poll.field_question"), required=True, max_length=200,
            placeholder=t(config, "poll.ph_question"))
        self.opzioni = discord.ui.TextInput(
            label=t(config, "poll.field_options"), required=True,
            style=discord.TextStyle.paragraph, max_length=1000,
            placeholder=t(config, "poll.ph_options"))
        for campo in (self.titolo, self.domanda, self.opzioni):
            self.add_item(campo)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        opzioni = parse_opzioni(self.opzioni.value)
        if len(opzioni) < 2:
            await interaction.response.send_message(
                t(config, "poll.need_two"), ephemeral=True)
            return
        v = PollPreviewView(self.cog, interaction.user.id, interaction.guild,
                            self.titolo.value.strip(), self.domanda.value.strip(), opzioni)
        await interaction.response.send_message(embed=v.build_embed(), view=v, ephemeral=True)


# ── PICKER EMOJI (da tutti i server del bot) ─────────────────────────────────
class EmojiOptionSelect(discord.ui.Select):
    """Sceglie a quale opzione assegnare l'emoji."""

    def __init__(self, opzioni, scelta):
        options = [
            discord.SelectOption(label=o["testo"][:100], value=str(i),
                                 emoji=_safe_emoji(o["emoji"]), default=(i == scelta))
            for i, o in enumerate(opzioni)
        ]
        super().__init__(placeholder="1️⃣ Option to change...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        v.scelta = int(self.values[0])
        await v.refresh(interaction)


class EmojiServerSelect(discord.ui.Select):
    """Emoji di tutti i server in cui si trova il bot, paginate."""

    def __init__(self, emojis, page):
        chunk = emojis[page * 25:page * 25 + 25]
        tot = max(1, (len(emojis) + 24) // 25)
        options = [discord.SelectOption(label=e.name[:100], value=str(e), emoji=e)
                   for e in chunk]
        super().__init__(placeholder=f"😀 Emoji — page {page + 1}/{tot}",
                         options=options or [discord.SelectOption(label="—")],
                         disabled=not options, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        v.opzioni[v.scelta]["emoji"] = self.values[0]
        await v.refresh(interaction)


class EmojiPageButton(discord.ui.Button):
    def __init__(self, delta, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=2)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        tot = max(1, (len(v.emojis) + 24) // 25)
        v.page = max(0, min(tot - 1, v.page + self.delta))
        await v.refresh(interaction)


class EmojiManualModal(discord.ui.Modal, title="Emoji by hand"):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.box = discord.ui.TextInput(
            label="Emoji", required=True, max_length=100,
            placeholder="😀   or   <:name:123456789>")
        self.add_item(self.box)

    async def on_submit(self, interaction: discord.Interaction):
        v = self.parent
        v.opzioni[v.scelta]["emoji"] = self.box.value.strip()
        await v.refresh(interaction)


class EmojiManualButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔤 By hand", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EmojiManualModal(self.view))


class EmojiBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        nv = PollPreviewView(v.cog, v.author_id, v.guild, v.titolo, v.domanda, v.opzioni)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


def _safe_emoji(raw):
    try:
        return discord.PartialEmoji.from_str(str(raw))
    except Exception:
        return None


class EmojiPickerView(discord.ui.View):
    def __init__(self, cog, author_id, guild, titolo, domanda, opzioni, scelta=0, page=0):
        super().__init__(timeout=300)
        self.cog, self.author_id, self.guild = cog, author_id, guild
        self.titolo, self.domanda, self.opzioni = titolo, domanda, opzioni
        self.scelta, self.page = scelta, page
        # Un bot può usare le emoji di QUALSIASI server in cui si trova.
        self.emojis = [e for g in cog.bot.guilds for e in g.emojis]

        self.add_item(EmojiOptionSelect(opzioni, scelta))
        if self.emojis:
            self.add_item(EmojiServerSelect(self.emojis, page))
            if len(self.emojis) > 25:
                self.add_item(EmojiPageButton(-1, "◀"))
                self.add_item(EmojiPageButton(1, "▶"))
        self.add_item(EmojiManualButton())
        self.add_item(EmojiBackButton())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                t(db.get_log_config(interaction.guild_id), "poll.only_author"), ephemeral=True)
            return False
        return True

    def build_embed(self):
        config = db.get_log_config(self.guild.id)
        righe = [f"{'▸' if i == self.scelta else '　'} {o['emoji']} {o['testo']}"
                 for i, o in enumerate(self.opzioni)]
        e = discord.Embed(title=t(config, "poll.emoji_title"),
                          description="\n".join(righe), color=BLU)
        e.set_footer(text=t(config, "poll.emoji_footer"))
        return e

    async def refresh(self, interaction):
        nv = EmojiPickerView(self.cog, self.author_id, self.guild, self.titolo,
                             self.domanda, self.opzioni, self.scelta, self.page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


# ── ANTEPRIMA + PUBBLICAZIONE ────────────────────────────────────────────────
class PollChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📢 Channel to publish in...",
                         channel_types=[discord.ChannelType.text],
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.canale = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PollEmojiButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="😀 Emoji", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        nv = EmojiPickerView(v.cog, v.author_id, v.guild, v.titolo, v.domanda, v.opzioni)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class PollPublishButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✅ Publish", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(interaction.guild_id)
        canale = v.guild.get_channel(v.canale) if v.canale else interaction.channel
        if canale is None:
            await interaction.response.send_message(t(config, "poll.no_channel"), ephemeral=True)
            return

        # Il numero si consuma solo ora: se annulli non lo sprechi.
        cfg = poll_cfg(config)
        numero = cfg.get("counter", 0) + 1
        titolo = v.titolo or t(config, "poll.auto_title", n=numero)

        try:
            msg = await canale.send(
                build_poll_text(titolo, v.domanda, v.opzioni, cfg.get("ping_role")),
                # senza questo Discord mostrerebbe il tag senza notificare nessuno
                allowed_mentions=discord.AllowedMentions(roles=True, everyone=False, users=False),
            )
        except discord.Forbidden:
            await interaction.response.send_message(t(config, "poll.no_perm"), ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                t(config, "poll.send_error", error=e), ephemeral=True)
            return

        if not v.titolo:                       # numerazione consumata solo se usata
            cfg["counter"] = numero
            db.save_log_config(interaction.guild_id, config)

        for o in v.opzioni:
            emo = _safe_emoji(o["emoji"])
            if emo is None:
                continue
            try:
                await msg.add_reaction(emo)
            except discord.HTTPException:
                pass

        await interaction.response.edit_message(
            content=t(config, "poll.published", channel=canale.mention),
            embed=None, view=None)


class PollPreviewView(discord.ui.View):
    def __init__(self, cog, author_id, guild, titolo, domanda, opzioni, canale=None):
        super().__init__(timeout=600)
        self.cog, self.author_id, self.guild = cog, author_id, guild
        self.titolo, self.domanda, self.opzioni = titolo, domanda, opzioni
        # Canale predefinito dalla dashboard: si può comunque cambiare qui sotto.
        if canale is None:
            canale = poll_cfg(db.get_log_config(guild.id)).get("channel")
        self.canale = canale
        self.add_item(PollChannelSelect())
        self.add_item(PollEmojiButton())
        self.add_item(PollPublishButton())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                t(db.get_log_config(interaction.guild_id), "poll.only_author"), ephemeral=True)
            return False
        return True

    def build_embed(self):
        config = db.get_log_config(self.guild.id)
        cfg = poll_cfg(config)
        numero = cfg.get("counter", 0) + 1
        titolo = self.titolo or t(config, "poll.auto_title", n=numero)
        ch = self.guild.get_channel(self.canale) if self.canale else None
        e = discord.Embed(
            title=t(config, "poll.preview_title"),
            description=build_poll_text(titolo, self.domanda, self.opzioni,
                                        cfg.get("ping_role")),
            color=BLU,
        )
        e.add_field(name=t(config, "common.channel"),
                    value=ch.mention if ch else t(config, "poll.channel_current"), inline=False)
        e.set_footer(text=t(config, "poll.preview_footer"))
        return e


# ── COG ──────────────────────────────────────────────────────────────────────
class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Visibile a tutti di proposito: chi può usarlo lo decidono i ruoli scelti
    # in dashboard, e con default_permissions quei ruoli non lo vedrebbero.
    @app_commands.command(name="poll", description="Create a poll with reactions")
    @app_commands.guild_only()
    async def poll(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        if not logconfig.feature_enabled(config, "poll"):
            await interaction.response.send_message(t(config, "poll.disabled"), ephemeral=True)
            return
        if not poll_allowed(config, interaction.user):
            await interaction.response.send_message(t(config, "poll.no_role"), ephemeral=True)
            return
        await interaction.response.send_modal(PollModal(self, config))


async def setup(bot):
    await bot.add_cog(Poll(bot))
