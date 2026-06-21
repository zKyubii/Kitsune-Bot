import discord
from discord.ext import commands

import database as db
import logconfig

BLU = 0x5865F2
PRIVACY_KINDS = ("avatar", "banner", "quote")


# ── HELPER PRIVACY (usati anche da avatar.py e quote.py) ────────────────────
def _privacy(prof: dict) -> dict:
    return prof.get("privacy", {})


def privacy_blocked(guild: discord.Guild, requester: discord.abc.User,
                    target: discord.abc.User, kind: str) -> bool:
    """True se 'requester' NON può vedere l'avatar/banner/quote di 'target'."""
    if requester.id == target.id:
        return False
    config = db.get_log_config(guild.id)
    # se l'intero sistema profilo è spento, niente blocchi privacy
    if not logconfig.feature_enabled(config, "profile"):
        return False
    prof = db.get_user_profile(target.id)
    if not _privacy(prof).get(kind, False):
        return False  # l'utente non ha bloccato questa cosa
    # i ruoli configurati in dashboard ignorano la privacy
    bypass = logconfig.privacy_bypass_roles(config)
    if bypass and any(r.id in bypass for r in getattr(requester, "roles", [])):
        return False
    return True


def privacy_notify(target: discord.abc.User) -> bool:
    """Se l'utente vuole che venga avvisato chi prova ad aprire una cosa bloccata."""
    return db.get_user_profile(target.id).get("notify", True)


# ── EMBED ───────────────────────────────────────────────────────────────────
def _bool_label(blocked: bool) -> str:
    return "🔴 Bloccato" if blocked else "🟢 Visibile"


def _custom_emojis_line(member, guild, config, prof) -> str:
    if not logconfig.custom_react_allowed(config, member.id):
        return "Non abilitate"
    emojis = prof.get("custom_emojis", [])
    return " ".join(emojis) if emojis else "Non impostate"


def build_home_embed(member: discord.Member, guild: discord.Guild,
                     config: dict, prof: dict) -> discord.Embed:
    e = discord.Embed(
        title=f"🦊 Profilo di {member.display_name}",
        description="⭐ Mini guida per configurare il tuo profilo e le funzioni del bot.\n"
                    "Usa il menu a tendina qui sotto per spostarti tra le sezioni.",
        color=member.color if member.color.value else BLU,
    )
    e.set_thumbnail(url=member.display_avatar.url)

    # Ruolo primario (lo assegni tu dalla dashboard)
    prid = logconfig.primary_role_of(config, member.id)
    role = guild.get_role(prid) if prid else None
    e.add_field(name="🏅 Ruolo primario",
                value=role.mention if role else "Nessuno", inline=False)

    pv = _privacy(prof)
    e.add_field(
        name="🔒 Privacy",
        value=(f"**Avatar:** {_bool_label(pv.get('avatar', False))}\n"
               f"**Banner:** {_bool_label(pv.get('banner', False))}\n"
               f"**Quote:** {_bool_label(pv.get('quote', False))}"),
        inline=False,
    )

    # Vocale privata assegnata
    vid = logconfig.private_voice_of(config, member.id)
    ch = guild.get_channel(vid) if vid else None
    e.add_field(name="🔊 Vocale Privata",
                value=ch.mention if ch else "Nessuna vocale", inline=False)

    e.add_field(name="⭐ Custom Reactions",
                value=_custom_emojis_line(member, guild, config, prof), inline=False)

    e.set_footer(text="Kitsune • Profilo")
    return e


# ── COMPONENTI ──────────────────────────────────────────────────────────────
class SectionSelect(discord.ui.Select):
    def __init__(self, current: str):
        options = [
            discord.SelectOption(label="Home", emoji="🏠", value="home",
                                 default=(current == "home")),
            discord.SelectOption(label="Privacy", emoji="🔒", value="privacy",
                                 default=(current == "privacy")),
            discord.SelectOption(label="Vocale Privata", emoji="🔊", value="voice",
                                 default=(current == "voice")),
            discord.SelectOption(label="Custom Reactions", emoji="⭐", value="react",
                                 default=(current == "react")),
        ]
        super().__init__(placeholder="Cambia sezione...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        dest = self.values[0]
        if dest == "privacy":
            nv = PrivacyView(v.author_id, v.guild, v.member)
        elif dest == "voice":
            nv = VoiceView(v.author_id, v.guild, v.member)
        elif dest == "react":
            nv = ReactView(v.author_id, v.guild, v.member)
        else:
            nv = HomeView(v.author_id, v.guild, v.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class CloseButton(discord.ui.Button):
    def __init__(self, row: int = 4):
        super().__init__(emoji="❌", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.message.delete()
        except (discord.HTTPException, discord.NotFound):
            await interaction.response.defer()


class _ProfileBase(discord.ui.View):
    def __init__(self, author_id: int, guild: discord.Guild, member: discord.Member,
                 current: str):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild = guild
        self.member = member
        self.add_item(SectionSelect(current))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo chi ha aperto il profilo può usarlo.", ephemeral=True)
            return False
        return True

    def _prof(self) -> dict:
        return db.get_user_profile(self.member.id)

    def _config(self) -> dict:
        return db.get_log_config(self.guild.id)


# ── HOME ──────────────────────────────────────────────────────────────────
class HomeView(_ProfileBase):
    def __init__(self, author_id, guild, member):
        super().__init__(author_id, guild, member, "home")
        self.add_item(CloseButton())

    def build_embed(self):
        return build_home_embed(self.member, self.guild, self._config(), self._prof())


# ── PRIVACY ────────────────────────────────────────────────────────────────
class PrivacyToggle(discord.ui.Button):
    def __init__(self, kind: str, blocked: bool, row: int):
        super().__init__(
            label=kind.capitalize(),
            emoji="🔴" if blocked else "🟢",
            style=discord.ButtonStyle.danger if blocked else discord.ButtonStyle.success,
            row=row,
        )
        self.kind = kind

    async def callback(self, interaction: discord.Interaction):
        prof = self.view._prof()
        priv = prof.setdefault("privacy", {})
        priv[self.kind] = not priv.get(self.kind, False)
        db.save_user_profile(self.view.member.id, prof)
        nv = PrivacyView(self.view.author_id, self.view.guild, self.view.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class PrivacyBulk(discord.ui.Button):
    def __init__(self, block: bool):
        super().__init__(
            label="Blocca tutto" if block else "Sblocca tutto",
            emoji="🔒" if block else "🔓",
            style=discord.ButtonStyle.secondary, row=2,
        )
        self.block = block

    async def callback(self, interaction: discord.Interaction):
        prof = self.view._prof()
        prof["privacy"] = {k: self.block for k in PRIVACY_KINDS}
        db.save_user_profile(self.view.member.id, prof)
        nv = PrivacyView(self.view.author_id, self.view.guild, self.view.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class NotifyToggle(discord.ui.Button):
    def __init__(self, on: bool):
        super().__init__(
            label="Notifica: ON" if on else "Notifica: OFF",
            emoji="🔔" if on else "🔕",
            style=discord.ButtonStyle.success if on else discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        prof = self.view._prof()
        prof["notify"] = not prof.get("notify", True)
        db.save_user_profile(self.view.member.id, prof)
        nv = PrivacyView(self.view.author_id, self.view.guild, self.view.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class PrivacyView(_ProfileBase):
    def __init__(self, author_id, guild, member):
        super().__init__(author_id, guild, member, "privacy")
        pv = self._privacy()
        for kind in PRIVACY_KINDS:
            self.add_item(PrivacyToggle(kind, pv.get(kind, False), row=1))
        self.add_item(PrivacyBulk(True))
        self.add_item(PrivacyBulk(False))
        self.add_item(NotifyToggle(self._prof().get("notify", True)))
        self.add_item(CloseButton())

    def _privacy(self):
        return self._prof().get("privacy", {})

    def build_embed(self):
        pv = self._privacy()
        notify = self._prof().get("notify", True)
        e = discord.Embed(
            title="🔒 Privacy",
            description="Gestisci chi può vedere il tuo **avatar/banner** e **citarti** (quote).\n"
                        "🟢 Visibile = tutti · 🔴 Bloccato = solo tu (e i ruoli staff abilitati).",
            color=self.member.color if self.member.color.value else BLU,
        )
        e.add_field(name="Avatar", value=_bool_label(pv.get("avatar", False)))
        e.add_field(name="Banner", value=_bool_label(pv.get("banner", False)))
        e.add_field(name="Quote", value=_bool_label(pv.get("quote", False)))
        e.add_field(
            name="🔔 Notifica",
            value=("Avviso chi prova ad aprire una cosa bloccata."
                   if notify else "Nessun avviso a chi ci prova."),
            inline=False,
        )
        e.set_footer(text="Kitsune • Profilo")
        return e


# ── VOCALE PRIVATA ─────────────────────────────────────────────────────────
class VoiceView(_ProfileBase):
    def __init__(self, author_id, guild, member):
        super().__init__(author_id, guild, member, "voice")
        self.add_item(CloseButton())

    def build_embed(self):
        vid = logconfig.private_voice_of(self._config(), self.member.id)
        ch = self.guild.get_channel(vid) if vid else None
        e = discord.Embed(
            title="🔊 Vocale Privata",
            color=self.member.color if self.member.color.value else BLU,
        )
        if ch:
            e.description = (f"La tua vocale privata è {ch.mention}.\n"
                            "Te l'ha assegnata lo staff: entra pure quando vuoi.")
        else:
            e.description = ("Non hai una vocale privata assegnata.\n"
                            "Viene assegnata dallo staff (es. con il doppio boost).")
        e.set_footer(text="Kitsune • Profilo")
        return e


# ── CUSTOM REACTIONS ───────────────────────────────────────────────────────
class ReactModal(discord.ui.Modal, title="Custom Reactions"):
    def __init__(self, member, guild, author_id, maxn):
        super().__init__()
        self.member = member
        self.guild = guild
        self.author_id = author_id
        self.maxn = maxn
        self.box = discord.ui.TextInput(
            label=f"Emoji (max {maxn}, separate da spazio)",
            placeholder="😎 🔥 <:nome:123456789>",
            required=False, max_length=200, style=discord.TextStyle.short,
        )
        self.add_item(self.box)

    async def on_submit(self, interaction: discord.Interaction):
        raw = (self.box.value or "").split()
        valid = []
        for tok in raw:
            try:
                discord.PartialEmoji.from_str(tok)
                valid.append(tok)
            except Exception:
                continue
            if len(valid) >= self.maxn:
                break
        prof = db.get_user_profile(self.member.id)
        prof["custom_emojis"] = valid
        db.save_user_profile(self.member.id, prof)
        nv = ReactView(self.author_id, self.guild, self.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactSetButton(discord.ui.Button):
    def __init__(self, maxn):
        super().__init__(label="Imposta emoji", emoji="✏️",
                         style=discord.ButtonStyle.primary, row=1)
        self.maxn = maxn

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        await interaction.response.send_modal(
            ReactModal(v.member, v.guild, v.author_id, self.maxn))


class ReactClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Rimuovi", emoji="🗑️",
                         style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        prof = self.view._prof()
        prof["custom_emojis"] = []
        db.save_user_profile(self.view.member.id, prof)
        nv = ReactView(self.view.author_id, self.view.guild, self.view.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactView(_ProfileBase):
    def __init__(self, author_id, guild, member):
        super().__init__(author_id, guild, member, "react")
        if logconfig.custom_react_allowed(self._config(), member.id):
            self.add_item(ReactSetButton(logconfig.custom_react_max(self._config())))
            self.add_item(ReactClearButton())
        self.add_item(CloseButton())

    def build_embed(self):
        config = self._config()
        allowed = logconfig.custom_react_allowed(config, self.member.id)
        e = discord.Embed(title="⭐ Custom Reactions",
                          color=self.member.color if self.member.color.value else BLU)
        if not allowed:
            e.description = ("Non sei abilitato alle custom reactions.\n"
                            "È un permesso che assegna lo staff dalla dashboard.")
        else:
            emojis = self._prof().get("custom_emojis", [])
            maxn = logconfig.custom_react_max(config)
            e.description = (
                f"Il bot reagisce ai tuoi messaggi con le emoji che scegli (max **{maxn}**).\n\n"
                f"**Attuali:** {' '.join(emojis) if emojis else 'Nessuna'}"
            )
        e.set_footer(text="Kitsune • Profilo")
        return e


# ── COG ─────────────────────────────────────────────────────────────────────
class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["profilo"])
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, target: discord.Member = None):
        config = db.get_log_config(ctx.guild.id)
        if not logconfig.feature_enabled(config, "profile"):
            await ctx.send("🚫 Il sistema profilo è disattivato su questo server.")
            return
        member = target or ctx.author
        # Sul profilo di un altro mostro solo la Home (sola lettura)
        if member.id != ctx.author.id:
            embed = build_home_embed(member, ctx.guild, config, db.get_user_profile(member.id))
            await ctx.send(embed=embed)
            return
        view = HomeView(ctx.author.id, ctx.guild, member)
        await ctx.send(embed=view.build_embed(), view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        config = db.get_log_config(message.guild.id)
        if not logconfig.feature_enabled(config, "profile"):
            return
        if not logconfig.custom_react_allowed(config, message.author.id):
            return
        emojis = db.get_user_profile(message.author.id).get("custom_emojis", [])
        for raw in emojis[:logconfig.custom_react_max(config)]:
            try:
                await message.add_reaction(discord.PartialEmoji.from_str(raw))
            except (discord.HTTPException, ValueError):
                pass


async def setup(bot):
    await bot.add_cog(Profile(bot))
