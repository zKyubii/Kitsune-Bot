import discord
from discord.ext import commands

import database as db
import logconfig
from locales import t


def _T(key: str, **kwargs) -> str:
    """Testo nella lingua del server corrente."""
    return t(_CTX.get("config"), key, **kwargs)


_CTX = {}


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
    return "🔴 Blocked" if blocked else "🟢 Visible"


def _custom_emojis_line(member, guild, config) -> str:
    if not logconfig.custom_react_allowed(config, member):
        return _T("prof.non_abilitate")
    r = logconfig.mention_rule_for(config, member.id)
    emojis = r.get("emojis", []) if r else []
    return " ".join(emojis) if emojis else "Not set"


def build_home_embed(member: discord.Member, guild: discord.Guild,
                     config: dict, prof: dict) -> discord.Embed:
    _CTX["config"] = config          # può essere chiamata anche senza una view
    e = discord.Embed(
        title=f"🪪 {member.display_name}'s profile",
        description=_T("prof.mini_guida_configurare_tuo_profilo") +
                    _T("prof.usa_menu_tendina_qui_sotto"),
        color=member.color if member.color.value else BLU,
    )
    e.set_thumbnail(url=member.display_avatar.url)

    # Ruolo primario (lo assegni tu dalla dashboard)
    prid = logconfig.primary_role_of(config, member.id)
    role = guild.get_role(prid) if prid else None
    e.add_field(name=_T("prof.ruolo_primario"),
                value=role.mention if role else "None", inline=False)

    pv = _privacy(prof)
    e.add_field(
        name=_T("prof.privacy"),
        value=(f"**Avatar:** {_bool_label(pv.get('avatar', False))}\n" +
               f"**Banner:** {_bool_label(pv.get('banner', False))}\n" +
               f"**Quote:** {_bool_label(pv.get('quote', False))}"),
        inline=False,
    )

    # Vocale privata assegnata
    vid = logconfig.private_voice_of(config, member.id)
    ch = guild.get_channel(vid) if vid else None
    e.add_field(name="🔊 Private voice channel",
                value=ch.mention if ch else _T("prof.nessuna_vocale"), inline=False)

    e.add_field(name="⭐ Custom reactions",
                value=_custom_emojis_line(member, guild, config), inline=False)

    e.set_footer(text="Kitsune • Profile")
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
            options.append(discord.SelectOption(label="Roles", emoji="🎭",
                                                value="roles", default=(current == "roles")))
        if show_react:
            options.append(discord.SelectOption(label="Custom reactions", emoji="⭐",
                                                value="react", default=(current == "react")))
        super().__init__(placeholder="Change section...", options=options, row=0)

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
        _CTX["config"] = config          # lingua del server per i componenti
        show_react = logconfig.custom_react_allowed(config, member)
        show_roles = bool(logconfig.role_categories(config))
        self.add_item(SectionSelect(current, show_react, show_roles))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                _T("prof.solo_chi_ha_aperto_profilo"), ephemeral=True)
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
            title=_T("prof.privacy"),
            description=_T("prof.gestisci_chi_puo_vedere_tuo") +
                        _T("prof.visibile_tutti_bloccato_solo_tu"),
            color=self.member.color if self.member.color.value else BLU,
        )
        e.add_field(name="Avatar", value=_bool_label(pv.get("avatar", False)))
        e.add_field(name="Banner", value=_bool_label(pv.get("banner", False)))
        e.add_field(name="Quote", value=_bool_label(pv.get("quote", False)))
        e.add_field(
            name="🔔 Notifica",
            value=(_T("prof.avviso_chi_prova_ad_aprire")
                   if notify else _T("prof.nessun_avviso_chi_ci_prova")),
            inline=False,
        )
        e.set_footer(text="Kitsune • Profile")
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
        ph = (f"😀 Server emoji (max {maxn}) — page {page + 1}/{tot}"
              if tot > 1 else f"😀 Pick server emoji (max {maxn})...")
        super().__init__(placeholder=ph, min_values=0, max_values=min(maxn, len(options)) or 1,
                         options=options or [discord.SelectOption(label="—")], row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(v.guild.id)
        r = logconfig.ensure_mention_rule(config, v.member.id, source="profile")
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


class ReactManualModal(discord.ui.Modal, title=_T("prof.emoji_mano")):
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
        r = logconfig.ensure_mention_rule(config, self.member.id, source="profile")
        r["emojis"] = parse_emojis(self.box.value, self.guild, self.maxn)
        db.save_log_config(self.guild.id, config)
        nv = ReactView(self.author_id, self.guild, self.member)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactManualButton(discord.ui.Button):
    def __init__(self, maxn):
        super().__init__(label=_T("prof.emoji_mano2"), style=discord.ButtonStyle.secondary, row=2)
        self.maxn = maxn

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        await interaction.response.send_modal(
            ReactManualModal(v.author_id, v.guild, v.member, self.maxn))


class ReactModeButton(discord.ui.Button):
    def __init__(self, mode):
        is_exact = mode == "exact"
        super().__init__(label=f"🔁 {'tag only' if is_exact else 'anywhere'}",
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        config = db.get_log_config(v.guild.id)
        r = logconfig.ensure_mention_rule(config, v.member.id, source="profile")
        r["mode"] = "contains" if r.get("mode") == "exact" else "exact"
        db.save_log_config(v.guild.id, config)
        nv = ReactView(v.author_id, v.guild, v.member, v.emoji_page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class ReactClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("prof.rimuovi"), style=discord.ButtonStyle.secondary, row=2)

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
                    self.add_item(ReactPageButton(-1, _T("prof.emoji2")))
                    self.add_item(ReactPageButton(1, _T("prof.emoji")))
            self.add_item(ReactManualButton(maxn))
            self.add_item(ReactModeButton(r.get("mode", "contains")))
            self.add_item(ReactClearButton())
        self.add_item(CloseButton())

    def build_embed(self):
        config = self._config()
        allowed = logconfig.custom_react_allowed(config, self.member)
        e = discord.Embed(title="⭐ Custom reactions",
                          color=self.member.color if self.member.color.value else BLU)
        if not allowed:
            e.description = (_T("prof.non_sei_abilitato_alle_custom") +
                            _T("prof.permesso_assegna_staff_dalla_dashboard"))
            e.set_footer(text="Kitsune • Profile")
            return e
        r = logconfig.mention_rule_for(config, self.member.id) or {}
        emojis = r.get("emojis", [])
        maxn = logconfig.custom_react_max(config)
        modo = (_T("prof.solo_quando_tag_solo") if r.get("mode") == "exact"
                else _T("prof.anche_se_taggato_dentro_frase"))
        e.description = (
            f"The bot reacts **when you get tagged** with the emoji you choose (max **{maxn}**).\n\n" +
            f"**Your emoji:** {' '.join(emojis) if emojis else 'None'}\n" +
            f"**Modalità:** {modo}"
        )
        e.set_footer(text=_T("prof.emoji_dal_menu_server_oppure"))
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
        super().__init__(placeholder=_T("prof.scegli_categoria"), options=options, row=1)

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
            placeholder=f"Your roles • {cat.get('name', 'Category')}"[:150],
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
                await v.member.add_roles(*add, reason=_T("prof.profile_ruoli"))
            if remove:
                await v.member.remove_roles(*remove, reason=_T("prof.profile_ruoli"))
        except discord.HTTPException:
            pass
        nv = RolesView(v.author_id, v.guild, v.member, self.cat_id)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class RoleClearButton(discord.ui.Button):
    def __init__(self, cat_id):
        super().__init__(label=_T("prof.rimuovi_ruoli"), emoji="🗑️",
                         style=discord.ButtonStyle.secondary, row=3)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        cat = logconfig.role_categories(db.get_log_config(v.guild.id)).get(self.cat_id, {})
        remove = [r for r in (v.guild.get_role(rid) for rid in cat.get("roles", []))
                  if r and r in v.member.roles and _assignable(v.guild, r)]
        if remove:
            try:
                await v.member.remove_roles(*remove, reason=_T("prof.profile_rimuovi_ruoli"))
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
        e = discord.Embed(title=_T("prof.ruoli"),
                          color=self.member.color if self.member.color.value else BLU)
        if not cats:
            e.description = _T("prof.nessuna_categoria_ruoli_configurata_dallo")
            e.set_footer(text="Kitsune • Profile")
            return e
        cat = cats.get(self.cat_id, {})
        modo = "scelta singola" if cat.get("single") else "scelta multipla"
        e.description = (_T("prof.scegli_categoria_dal_menu_poi") +
                         f"Categoria attuale: **{cat.get('name', '—')}** ({modo}).")
        roles = [r for r in (self.guild.get_role(rid) for rid in cat.get("roles", [])) if r]
        miei = [r.mention for r in roles if r in self.member.roles]
        e.add_field(name=_T("prof.tuoi_ruoli_qui"),
                    value=" ".join(miei) if miei else "*Nessuno*", inline=False)
        e.set_footer(text="Kitsune • Profile")
        return e


# ── COG ─────────────────────────────────────────────────────────────────────
class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Se l'utente perde il ruolo che abilita le custom reactions, togliamo
        # anche la sua reaction-al-tag (oltre alla possibilità di impostarla).
        if before.roles == after.roles:
            return
        config = db.get_log_config(after.guild.id)
        if logconfig.custom_react_allowed(config, before) and \
                not logconfig.custom_react_allowed(config, after):
            if logconfig.remove_profile_mention_rule(config, after.id):
                db.save_log_config(after.guild.id, config)

    @commands.command(name="profile", aliases=["profilo"])
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, target: discord.Member = None):
        config = db.get_log_config(ctx.guild.id)
        if not logconfig.feature_enabled(config, "profile"):
            await ctx.send(_T("prof.sistema_profilo_disattivato_questo_server"))
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
