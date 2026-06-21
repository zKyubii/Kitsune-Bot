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


def _custom_emojis_line(member, guild, config) -> str:
    if not logconfig.custom_react_allowed(config, member):
        return "Non abilitate"
    r = logconfig.mention_rule_for(config, member.id)
    emojis = r.get("emojis", []) if r else []
    return " ".join(emojis) if emojis else "Non impostate"


def build_home_embed(member: discord.Member, guild: discord.Guild,
                     config: dict, prof: dict) -> discord.Embed:
    e = discord.Embed(
        title=f"🪪 Profilo di {member.display_name}",
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
                value=_custom_emojis_line(member, guild, config), inline=False)

    e.set_footer(text="Kitsune • Profilo")
    return e


# ── COMPONENTI ──────────────────────────────────────────────────────────────
class SectionSelect(discord.ui.Select):
    def __init__(self, current: str, show_react: bool, show_roles: bool):
        options = [
            discord.SelectOption(label="Home", emoji="🏠", value="home",
                                 default=(current == "home")),
            discord.SelectOption(label="Privacy", emoji="🔒", value="privacy",
                                 default=(current == "privacy")),
        ]
        if show_roles:
            options.append(discord.SelectOption(label="Ruoli", emoji="🎭",
                                                value="roles", default=(current == "roles")))
        if show_react:
            options.append(discord.SelectOption(label="Custom Reactions", emoji="⭐",
                                                value="react", default=(current == "react")))
        super().__init__(placeholder="Cambia sezione...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        dest = self.values[0]
        if dest == "privacy":
            nv = PrivacyView(v.author_id, v.guild, v.member)
        elif dest == "roles":
            nv = RolesView(v.author_id, v.guild, v.member)
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
        config = db.get_log_config(guild.id)
        show_react = logconfig.custom_react_allowed(config, member)
        show_roles = bool(logconfig.role_categories(config))
        self.add_item(SectionSelect(current, show_react, show_roles))

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


# ── CUSTOM REACTIONS ───────────────────────────────────────────────────────
def parse_emojis(testo, guild, maxn):
    """Estrae fino a maxn emoji: unicode, <:nome:id> o solo il NOME (es. 'fuoco')."""
    out = []
    for tok in (testo or "").split():
        tok = tok.strip()
        if not tok:
            continue
        if guild and not tok.startswith("<"):
            name = tok.strip(":")
            match = next((e for e in guild.emojis if e.name.lower() == name.lower()), None)
            if match:
                out.append(str(match))
                if len(out) >= maxn:
                    break
                continue
        out.append(tok)
        if len(out) >= maxn:
            break
    return out


class ReactServerEmojiSelect(discord.ui.Select):
    def __init__(self, guild, current, maxn, page=0):
        self.page = page
        self.maxn = maxn
        emojis = guild.emojis
        chunk = emojis[page * 25:page * 25 + 25]
        self._page_strs = {str(e) for e in chunk}
        cur = set(current)
        options = [discord.SelectOption(label=e.name[:100], value=str(e), emoji=e, default=str(e) in cur)
                   for e in chunk]
        tot = max(1, (len(emojis) + 24) // 25)
        ph = (f"😀 Emoji dal server (max {maxn}) — pag {page + 1}/{tot}"
              if tot > 1 else f"😀 Scegli emoji dal server (max {maxn})...")
        super().__init__(placeholder=ph, min_values=0, max_values=min(maxn, len(options)) or 1,
                         options=options or [discord.SelectOption(label="—")], row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(v.guild.id)
        r = logconfig.ensure_mention_rule(config, v.member.id)
        # conserva le emoji scelte in altre pagine / a mano, aggiorna solo questa pagina
        altri = [e for e in r.get("emojis", []) if e not in self._page_strs]
        r["emojis"] = (altri + list(self.values))[:self.maxn]
        db.save_log_config(v.guild.id, config)
        nv = ReactView(v.author_id, v.guild, v.member, self.page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactPageButton(discord.ui.Button):
    def __init__(self, delta, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=2)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        tot = max(1, (len(v.guild.emojis) + 24) // 25)
        new_page = max(0, min(tot - 1, v.emoji_page + self.delta))
        nv = ReactView(v.author_id, v.guild, v.member, new_page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactManualModal(discord.ui.Modal, title="Emoji a mano"):
    def __init__(self, author_id, guild, member, maxn):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.member = member
        self.maxn = maxn
        r = logconfig.mention_rule_for(db.get_log_config(guild.id), member.id) or {}
        self.box = discord.ui.TextInput(
            label=f"Emoji o nomi (max {maxn}, separati da spazio)", required=False,
            default=" ".join(r.get("emojis", [])),
            placeholder="😀  :nome:  fuoco  <:custom:123>", max_length=200)
        self.add_item(self.box)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(self.guild.id)
        r = logconfig.ensure_mention_rule(config, self.member.id)
        r["emojis"] = parse_emojis(self.box.value, self.guild, self.maxn)
        db.save_log_config(self.guild.id, config)
        nv = ReactView(self.author_id, self.guild, self.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactManualButton(discord.ui.Button):
    def __init__(self, maxn):
        super().__init__(label="🔤 Emoji a mano", style=discord.ButtonStyle.secondary, row=2)
        self.maxn = maxn

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        await interaction.response.send_modal(
            ReactManualModal(v.author_id, v.guild, v.member, self.maxn))


class ReactModeButton(discord.ui.Button):
    def __init__(self, mode):
        is_exact = mode == "exact"
        super().__init__(label=f"🔁 {'solo il tag' if is_exact else 'ovunque'}",
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(v.guild.id)
        r = logconfig.ensure_mention_rule(config, v.member.id)
        r["mode"] = "contains" if r.get("mode") == "exact" else "exact"
        db.save_log_config(v.guild.id, config)
        nv = ReactView(v.author_id, v.guild, v.member, v.emoji_page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🗑️ Rimuovi", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(v.guild.id)
        logconfig.remove_mention_rule(config, v.member.id)
        db.save_log_config(v.guild.id, config)
        nv = ReactView(v.author_id, v.guild, v.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactView(_ProfileBase):
    def __init__(self, author_id, guild, member, emoji_page=0):
        super().__init__(author_id, guild, member, "react")
        self.emoji_page = emoji_page
        config = self._config()
        if logconfig.custom_react_allowed(config, member):
            maxn = logconfig.custom_react_max(config)
            r = logconfig.mention_rule_for(config, member.id) or {}
            cur = r.get("emojis", [])
            if guild.emojis:
                self.add_item(ReactServerEmojiSelect(guild, cur, maxn, emoji_page))
                if len(guild.emojis) > 25:
                    self.add_item(ReactPageButton(-1, "◀ Emoji"))
                    self.add_item(ReactPageButton(1, "Emoji ▶"))
            self.add_item(ReactManualButton(maxn))
            self.add_item(ReactModeButton(r.get("mode", "contains")))
            self.add_item(ReactClearButton())
        self.add_item(CloseButton())

    def build_embed(self):
        config = self._config()
        allowed = logconfig.custom_react_allowed(config, self.member)
        e = discord.Embed(title="⭐ Custom Reactions",
                          color=self.member.color if self.member.color.value else BLU)
        if not allowed:
            e.description = ("Non sei abilitato alle custom reactions.\n"
                            "È un permesso che assegna lo staff dalla dashboard.")
            e.set_footer(text="Kitsune • Profilo")
            return e
        r = logconfig.mention_rule_for(config, self.member.id) or {}
        emojis = r.get("emojis", [])
        maxn = logconfig.custom_react_max(config)
        modo = ("solo quando il tag è da solo" if r.get("mode") == "exact"
                else "anche se taggato dentro una frase")
        e.description = (
            f"Il bot reagisce **quando vieni taggato** con le emoji che scegli (max **{maxn}**).\n\n"
            f"**Le tue emoji:** {' '.join(emojis) if emojis else 'Nessuna'}\n"
            f"**Modalità:** {modo}"
        )
        e.set_footer(text="Emoji dal menu (server) oppure 'Emoji a mano' per unicode/altre.")
        return e


# ── RUOLI (self-role a categorie) ──────────────────────────────────────────
def _assignable(guild: discord.Guild, role: discord.Role) -> bool:
    return bool(role) and not role.managed and not role.is_default() and role < guild.me.top_role


def _safe_emoji(raw):
    if not raw:
        return None
    try:
        return discord.PartialEmoji.from_str(str(raw))
    except Exception:
        return None


class RoleCategoryPicker(discord.ui.Select):
    def __init__(self, cats: dict, current):
        options = []
        for cid, c in list(cats.items())[:25]:
            options.append(discord.SelectOption(
                label=c.get("name", "Categoria")[:100], value=cid,
                description="Scelta singola" if c.get("single") else "Scelta multipla",
                emoji=_safe_emoji(c.get("emoji")), default=(cid == current)))
        super().__init__(placeholder="Scegli una categoria...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        nv = RolesView(v.author_id, v.guild, v.member, self.values[0])
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class RoleOptionSelect(discord.ui.Select):
    def __init__(self, cat_id, cat, roles, member):
        self.cat_id = cat_id
        self.cat_role_ids = [r.id for r in roles]
        single = cat.get("single", False)
        member_ids = {r.id for r in member.roles}
        options, scelto = [], False
        for r in roles:
            on = r.id in member_ids
            if single and on and scelto:
                on = False  # in scelta singola evidenzio un solo ruolo
            if single and on:
                scelto = True
            options.append(discord.SelectOption(label=r.name[:100], value=str(r.id), default=on))
        super().__init__(
            placeholder=f"I tuoi ruoli • {cat.get('name', 'Categoria')}"[:150],
            min_values=0, max_values=1 if single else len(options),
            options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        chosen = {int(x) for x in self.values}
        add, remove = [], []
        for rid in self.cat_role_ids:
            role = v.guild.get_role(rid)
            if not _assignable(v.guild, role):
                continue
            has = role in v.member.roles
            if rid in chosen and not has:
                add.append(role)
            elif rid not in chosen and has:
                remove.append(role)
        try:
            if add:
                await v.member.add_roles(*add, reason="+profile ruoli")
            if remove:
                await v.member.remove_roles(*remove, reason="+profile ruoli")
        except discord.HTTPException:
            pass
        nv = RolesView(v.author_id, v.guild, v.member, self.cat_id)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class RoleClearButton(discord.ui.Button):
    def __init__(self, cat_id):
        super().__init__(label="Rimuovi ruoli", emoji="🗑️",
                         style=discord.ButtonStyle.secondary, row=3)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        cat = logconfig.role_categories(db.get_log_config(v.guild.id)).get(self.cat_id, {})
        remove = [r for r in (v.guild.get_role(rid) for rid in cat.get("roles", []))
                  if r and r in v.member.roles and _assignable(v.guild, r)]
        if remove:
            try:
                await v.member.remove_roles(*remove, reason="+profile rimuovi ruoli")
            except discord.HTTPException:
                pass
        nv = RolesView(v.author_id, v.guild, v.member, self.cat_id)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class RolesView(_ProfileBase):
    def __init__(self, author_id, guild, member, cat_id=None):
        super().__init__(author_id, guild, member, "roles")
        cats = logconfig.role_categories(self._config())
        if cat_id not in cats:
            cat_id = next(iter(cats), None)
        self.cat_id = cat_id
        if cats:
            self.add_item(RoleCategoryPicker(cats, cat_id))
        if cat_id:
            roles = [r for r in (guild.get_role(rid) for rid in cats[cat_id].get("roles", [])) if r]
            if roles:
                self.add_item(RoleOptionSelect(cat_id, cats[cat_id], roles, member))
                self.add_item(RoleClearButton(cat_id))
        self.add_item(CloseButton())

    def build_embed(self):
        cats = logconfig.role_categories(self._config())
        e = discord.Embed(title="🎭 Ruoli",
                          color=self.member.color if self.member.color.value else BLU)
        if not cats:
            e.description = "Nessuna categoria di ruoli configurata dallo staff."
            e.set_footer(text="Kitsune • Profilo")
            return e
        cat = cats.get(self.cat_id, {})
        modo = "scelta singola" if cat.get("single") else "scelta multipla"
        e.description = ("Scegli la **categoria** dal menu, poi i tuoi ruoli.\n"
                         f"Categoria attuale: **{cat.get('name', '—')}** ({modo}).")
        roles = [r for r in (self.guild.get_role(rid) for rid in cat.get("roles", [])) if r]
        miei = [r.mention for r in roles if r in self.member.roles]
        e.add_field(name="I tuoi ruoli qui",
                    value=" ".join(miei) if miei else "*Nessuno*", inline=False)
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


async def setup(bot):
    await bot.add_cog(Profile(bot))
