import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db
import levelsystem as ls
from logconfig import (LOG_CATEGORIES, FEATURES, SPAM_CATEGORIES, SANCTIONS, categoria_cfg,
                       ensure_mention_rule, custom_react_allowed, remove_profile_mention_rule)
from locales import t

BLU = 0x5865F2


def build_main_embed(guild: discord.Guild, config: dict) -> discord.Embed:
    embed = discord.Embed(
        title=_T("dash.dashboard_configurazione"),
        description=_T("dash.seleziona_sezione_dal_menu"),
        color=BLU,
    )
    embed.add_field(
        name=_T("dash.sezioni_disponibili"),
        value=(
            _T("dash2.log_canali_ed_eventi_log") +
            _T("dash2.funzioni_attiva_disattiva_funzioni_bot") +
            _T("dash2.moderazione_regole_automatiche_warn_n") +
            _T("dash2.livelli_sistema_xp_premi_classifica")
        ),
        inline=False,
    )
    embed.set_footer(text=_T("dash.modifiche_vengono_salvate_automaticamente"))
    return embed


# ── COMPONENTI ────────────────────────────────────────────────────────────────
class BackButton(discord.ui.Button):
    def __init__(self, destination: str = "home"):
        super().__init__(label=_T("dash.indietro"), emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
        self.destination = destination

    async def callback(self, interaction: discord.Interaction):
        if self.destination == "logs":
            view = LogsMenuView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "features":
            view = FeaturesView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "mod":
            view = ModerationView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "antispam":
            view = AntispamView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "categories":
            view = SpamCategoriesView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "levels":
            view = LevelsView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "profile":
            view = ProfileDashView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "rolecats":
            view = RoleCategoriesView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        elif self.destination == "staff":
            view = StaffView(self.view.author_id, self.view.guild)
            embed = view.build_embed()
        else:
            view = DashboardView(self.view.author_id, self.view.guild)
            embed = build_main_embed(self.view.guild, db.get_log_config(self.view.guild.id))
        await interaction.response.edit_message(embed=embed, view=view)


class HomeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=_T("dash.log"), value="logs",
                                 description=_T("dash.configura_canali_eventi_log")),
            discord.SelectOption(label=_T("dash.funzioni"), value="features",
                                 description=_T("dash.attiva_o_disattiva_funzioni")),
            discord.SelectOption(label=_T("dash.moderazione"), value="mod",
                                 description=_T("dash.antispam_jail_warn_lock")),
            discord.SelectOption(label=_T("dash.livelli"), value="levels",
                                 description=_T("dash.sistema_xp_premi_multiplier")),
        ]
        super().__init__(placeholder=_T("dash.scegli_sezione"), options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "logs":
            view = LogsMenuView(self.view.author_id, self.view.guild)
        elif self.values[0] == "mod":
            view = ModerationView(self.view.author_id, self.view.guild)
        elif self.values[0] == "levels":
            view = LevelsView(self.view.author_id, self.view.guild)
        else:
            view = FeaturesView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class LogCategorySelect(discord.ui.Select):
    def __init__(self, config=None):
        options = [
            discord.SelectOption(label=t(config, label), value=key)
            for key, (label, _) in LOG_CATEGORIES.items()
        ]
        super().__init__(placeholder=t(config, "dash.log_cat_placeholder"), options=options)

    async def callback(self, interaction: discord.Interaction):
        view = CategoryView(self.view.author_id, self.view.guild, self.values[0])
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, category: str):
        super().__init__(
            placeholder=_T("dash.scegli_canale_log_questa"),
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1, row=0,
        )
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("logs", {}).setdefault(self.category, {})
        config["logs"][self.category]["channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        new_view = CategoryView(self.view.author_id, self.view.guild, self.category)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class EventiSelect(discord.ui.Select):
    def __init__(self, category: str, guild_id: int):
        self.category = category
        _, events = LOG_CATEGORIES[category]
        config = db.get_log_config(guild_id)
        enabled = config.get("logs", {}).get(category, {}).get("events", {})
        options = [
            discord.SelectOption(label=t(config, elabel), value=ek, default=enabled.get(ek, False))
            for ek, elabel in events.items()
        ]
        super().__init__(
            placeholder=_T("dash.scegli_eventi_registrare"),
            min_values=0, max_values=len(options), options=options, row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("logs", {}).setdefault(self.category, {})
        _, events = LOG_CATEGORIES[self.category]
        config["logs"][self.category]["events"] = {ek: (ek in self.values) for ek in events}
        db.save_log_config(interaction.guild_id, config)
        new_view = CategoryView(self.view.author_id, self.view.guild, self.category)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class QuoteChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder=_T("dash.scegli_canale_dove_pubblicare"),
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1, row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config["quote_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        new_view = QuoteSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class QuoteResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.usa_canale_comando"), emoji="♻️",
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config["quote_channel"] = None
        db.save_log_config(interaction.guild_id, config)
        new_view = QuoteSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


# ── REGOLE AUTO-WARN ──────────────────────────────────────────────────────────
def _fmt_sec(s: int) -> str:
    if s % 86400 == 0:
        return f"{s // 86400}g"
    if s % 3600 == 0:
        return f"{s // 3600}h"
    if s % 60 == 0:
        return f"{s // 60}min"
    return f"{s}s"


def _desc_azione(action: str, seconds: int = 0) -> str:
    if action == "timeout":
        return f"Timeout {_fmt_sec(seconds)}"
    if action == "kick":
        return "Kick"
    if action == "ban":
        return "Ban"
    return action


class WarnCountSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=f"{i} warn", value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder=_T("dash.1_numero_warn"), options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_count = int(self.values[0])
        await self.view.refresh(interaction)


class WarnActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=_T("dash.timeout_10_minuti"), value="timeout:600"),
            discord.SelectOption(label=_T("dash.timeout_1_ora"), value="timeout:3600"),
            discord.SelectOption(label=_T("dash.timeout_12_ore"), value="timeout:43200"),
            discord.SelectOption(label=_T("dash.timeout_1_giorno"), value="timeout:86400"),
            discord.SelectOption(label=_T("dash.kick"), value="kick:0"),
            discord.SelectOption(label=_T("dash.ban"), value="ban:0"),
        ]
        super().__init__(placeholder=_T("dash.2_azione_applicare"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        azione, secondi = self.values[0].split(":")
        self.view.pending_action = azione
        self.view.pending_seconds = int(secondi)
        await self.view.refresh(interaction)


class AddRuleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.aggiungi_regola"), emoji="➕", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if v.pending_count is None or v.pending_action is None:
            await interaction.response.send_message(
                _T("dash2.scegli_prima_numero_warn_l"), ephemeral=True)
            return
        config = db.get_log_config(interaction.guild_id)
        regole = [r for r in config.get("warn_actions", []) if r["count"] != v.pending_count]
        regole.append({"count": v.pending_count, "action": v.pending_action, "seconds": v.pending_seconds})
        regole.sort(key=lambda r: r["count"])
        config["warn_actions"] = regole
        db.save_log_config(interaction.guild_id, config)
        new_view = WarnActionsView(v.author_id, v.guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class RemoveRuleSelect(discord.ui.Select):
    def __init__(self, regole):
        options = [
            discord.SelectOption(label=f"{r['count']} warn → {_desc_azione(r['action'], r['seconds'])}",
                                 value=str(r["count"]))
            for r in regole
        ]
        super().__init__(placeholder=_T("dash.rimuovi_regola"), options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        config = db.get_log_config(interaction.guild_id)
        config["warn_actions"] = [r for r in config.get("warn_actions", []) if r["count"] != count]
        db.save_log_config(interaction.guild_id, config)
        new_view = WarnActionsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


# ── VIEW ──────────────────────────────────────────────────────────────────────
# Config del server della view attualmente in costruzione.
# BaseView.__init__ la imposta PRIMA che la sottoclasse aggiunga i componenti,
# così ogni Select/Button può tradurre le proprie etichette senza doversi far
# passare la config nel costruttore. È sicuro perché costruire una view è
# un'operazione sincrona: non c'è nessun await che possa interlacciare due view.
_CTX = {"config": None}


def _T(key: str, **kwargs) -> str:
    """Testo nella lingua del server della view in costruzione."""
    return t(_CTX["config"], key, **kwargs)


class BaseView(discord.ui.View):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild = guild
        self.config = db.get_log_config(guild.id)
        _CTX["config"] = self.config

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                t(db.get_log_config(interaction.guild_id), "dash.only_owner"), ephemeral=True
            )
            return False
        return True


class DashboardView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(HomeSelect())


class OpenLogBlacklistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.canali_blacklist"), emoji="📵", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BlacklistChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.canali_esclusi_dai_log"),
                         channel_types=[discord.ChannelType.text, discord.ChannelType.voice],
                         min_values=0, max_values=25, row=0,
                         default_values=_dv(ids, discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("log_blacklist", {})["channels"] = [c.id for c in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BlacklistSecretSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_segreto_dove_mandare"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("log_blacklist", {})["secret_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BlacklistSecretResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.ignora_invece_redirigere"), emoji="🚫",
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("log_blacklist", {})["secret_channel"] = None
        db.save_log_config(interaction.guild_id, config)
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LogBlacklistView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        bl = db.get_log_config(guild.id).get("log_blacklist", {})
        self.add_item(BlacklistChannelsSelect(bl.get("channels", [])))
        self.add_item(BlacklistSecretSelect())
        self.add_item(BlacklistSecretResetButton())
        self.add_item(BackButton("logs"))

    def build_embed(self) -> discord.Embed:
        bl = db.get_log_config(self.guild.id).get("log_blacklist", {})
        chans = bl.get("channels", [])
        secret = bl.get("secret_channel")
        embed = discord.Embed(
            title=_T("dash.canali_blacklist_log"),
            description=(_T("dash2.log_canali_selezionati_non_finiscono") +
                         _T("dash2.se_imposti_canale_segreto_vengono")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.canali_esclusi"), value=f"{len(chans)} channels" if chans else _T("dash2.nessuno"), inline=False)
        embed.add_field(name=_T("dash.canale_segreto"),
                        value=f"<#{secret}>" if secret else "None (logs are ignored)", inline=False)
        return embed


class LogsMenuView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(LogCategorySelect(db.get_log_config(guild.id)))
        self.add_item(OpenLogBlacklistButton())
        self.add_item(BackButton("home"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        logs = config.get("logs", {})
        righe = []
        for key, (label, events) in LOG_CATEGORIES.items():
            cat = logs.get(key, {})
            ch = cat.get("channel")
            if ch:
                attivi = sum(1 for v in cat.get("events", {}).values() if v)
                stato = f"<#{ch}> • {attivi}/{len(events)} events enabled"
            else:
                stato = _T("dash2.non_configurato")
            righe.append(f"**{t(config, label)}** — {stato}")
        embed = discord.Embed(
            title=_T("dash.log"),
            description=_T("dash.scegli_categoria_dal_menu"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.categorie"), value="\n".join(righe), inline=False)
        return embed


class CategoryView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, category: str):
        super().__init__(author_id, guild)
        self.category = category
        self.add_item(LogChannelSelect(category))
        self.add_item(EventiSelect(category, guild.id))
        self.add_item(BackButton("logs"))

    def build_embed(self) -> discord.Embed:
        label, events = LOG_CATEGORIES[self.category]
        config = db.get_log_config(self.guild.id)
        cat = config.get("logs", {}).get(self.category, {})
        ch = cat.get("channel")
        eventi_cfg = cat.get("events", {}) if ch else {}

        righe = [
            f"{'🟢' if eventi_cfg.get(ek, False) else '🔴'} {t(config, elabel)}"
            for ek, elabel in events.items()
        ]
        embed = discord.Embed(title=t(config, "dash.configura_log", cat=t(config, label)), color=BLU)
        embed.add_field(name=_T("dash.canale"),
                        value=f"<#{ch}>" if ch else _T("dash2.non_impostato"), inline=False)
        embed.add_field(name=_T("dash.eventi"), value="\n".join(righe), inline=False)
        embed.set_footer(text=_T("dash.scegli_canale_spunta_eventi"))
        return embed


class QuoteSettingsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        feats = db.get_log_config(guild.id).get("features", {})
        self.add_item(FeatureToggleButton("quote", feats.get("quote", True)))
        self.add_item(QuoteChannelSelect())
        self.add_item(QuoteResetButton())
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        attiva = _T("dash2.attiva") if config.get("features", {}).get("quote", True) else _T("dash2.disattivata")
        cid = config.get("quote_channel")
        dove = f"<#{cid}> (fixed channel)" if cid else "In the channel where the command is used"
        embed = discord.Embed(
            title=_T("dash.quote"),
            description=_T("dash.attiva_disattiva_funzione_scegli"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.destinazione"), value=dove, inline=False)
        return embed


class WarnActionsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.pending_count = None
        self.pending_action = None
        self.pending_seconds = 0
        self.add_item(WarnCountSelect())
        self.add_item(WarnActionSelect())
        self.add_item(AddRuleButton())
        regole = db.get_log_config(guild.id).get("warn_actions", [])
        if regole:
            self.add_item(RemoveRuleSelect(regole))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        regole = config.get("warn_actions", [])
        if regole:
            righe = [f"🔸 **{r['count']} warn** → {_desc_azione(r['action'], r['seconds'])}" for r in regole]
            testo = "\n".join(righe)
        else:
            testo = _T("dash2.nessuna_regola_impostata")

        embed = discord.Embed(
            title=_T("dash.regole_automatiche_warn"),
            description=_T("dash.imposta_azione_automatica_al"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.regole_attive"), value=testo, inline=False)
        if self.pending_count is not None or self.pending_action is not None:
            c = self.pending_count if self.pending_count is not None else "?"
            a = _desc_azione(self.pending_action, self.pending_seconds) if self.pending_action else "?"
            embed.add_field(name=_T("dash.nuova_regola"), value=f"{c} warn → {a}", inline=False)
        embed.set_footer(text=_T("dash.scegli_numero_azione_poi"))
        return embed

    async def refresh(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class DMLockButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label=_T("dash.dm_lock"), emoji="🔒",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        try:
            if guild.dms_paused():
                await guild.edit(dms_disabled_until=None)
                nuovo = None
            else:
                nuovo = discord.utils.utcnow() + datetime.timedelta(hours=24)
                await guild.edit(dms_disabled_until=nuovo)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Errore: {e}", ephemeral=True)
            return
        if guild._incidents_data is None:
            guild._incidents_data = {}
        guild._incidents_data["dms_disabled_until"] = nuovo.isoformat() if nuovo else None
        new_view = DMLockView(self.view.author_id, guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class JoinLockButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label=_T("dash.join_lock"), emoji="🚪",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        try:
            if guild.invites_paused():
                await guild.edit(invites_disabled_until=None)
                nuovo = None
            else:
                nuovo = discord.utils.utcnow() + datetime.timedelta(hours=24)
                await guild.edit(invites_disabled_until=nuovo)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Errore: {e}", ephemeral=True)
            return
        if guild._incidents_data is None:
            guild._incidents_data = {}
        guild._incidents_data["invites_disabled_until"] = nuovo.isoformat() if nuovo else None
        new_view = JoinLockView(self.view.author_id, guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


class SetupJailButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.setup"), emoji="🛠️", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = db.get_log_config(guild.id)
        jc = config.get("jail", {})
        role = guild.get_role(jc.get("role")) if jc.get("role") else None
        channel = guild.get_channel(jc.get("channel")) if jc.get("channel") else None

        if role and channel:
            await interaction.response.send_message(
                _T("dash2.jail_gia_configurato_usa_aggiorna"),
                ephemeral=True)
            return

        await interaction.response.defer()
        try:
            if not role:
                role = await guild.create_role(name=_T("dash.jailed"), colour=discord.Colour.dark_grey(),
                                               reason=_T("dash2.setup_jail"))
            if not channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                      read_message_history=True),
                }
                channel = await guild.create_text_channel("jail", overwrites=overwrites, reason=_T("dash2.setup_jail"))

            for ch in guild.channels:
                if ch.id == channel.id:
                    continue
                try:
                    await ch.set_permissions(role, view_channel=False, reason=_T("dash2.setup_jail"))
                except discord.HTTPException:
                    pass

            await channel.set_permissions(guild.default_role, view_channel=False)
            await channel.set_permissions(role, view_channel=True, send_messages=True, read_message_history=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Errore durante il setup: {e}", ephemeral=True)
            return

        config["jail"] = {"role": role.id, "channel": channel.id}
        db.save_log_config(guild.id, config)

        v = JailView(self.view.author_id, guild)
        await interaction.edit_original_response(embed=v.build_embed(), view=v)


class UpdateJailButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.aggiorna_canali"), emoji="🔄", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = db.get_log_config(guild.id)
        jc = config.get("jail", {})
        role = guild.get_role(jc.get("role")) if jc.get("role") else None
        if not role:
            await interaction.response.send_message(
                _T("dash2.devi_prima_fare_setup_jail"), ephemeral=True)
            return

        await interaction.response.defer()
        for ch in guild.channels:
            if ch.id == jc.get("channel"):
                continue
            try:
                await ch.set_permissions(role, view_channel=False, reason=_T("dash2.jail_aggiornamento_canali"))
            except discord.HTTPException:
                pass
        await interaction.followup.send(_T("dash2.canali_aggiornati_ruolo_jailed_nascosto"), ephemeral=True)


class JailLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_log_jail_unjail"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("jail", {})["log_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = JailView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class JailView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(SetupJailButton())
        self.add_item(UpdateJailButton())
        self.add_item(JailLogSelect())
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        jc = config.get("jail", {})
        role = self.guild.get_role(jc.get("role")) if jc.get("role") else None
        channel = self.guild.get_channel(jc.get("channel")) if jc.get("channel") else None
        log = self.guild.get_channel(jc.get("log_channel")) if jc.get("log_channel") else None

        if role and channel:
            stato = f"✅ Configured\n🎭 Role: {role.mention}\n📁 Channel: {channel.mention}"
        else:
            stato = _T("dash2.non_configurato_premi_setup_crearlo")
        log_txt = log.mention if log else _T("dash2.non_impostato")

        embed = discord.Embed(
            title=_T("dash.jail2"),
            description=(
                _T("dash2.sistema_isolamento_chi_jail_vede") +
                _T("dash2.setup_crea_ruolo_jailed_canale") +
                _T("dash2.aggiorna_canali_ri_applica_permissioni") +
                _T("dash2.comandi_jail_unjail_jailed")
            ),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=stato, inline=False)
        embed.add_field(name=_T("dash.canale_log"), value=log_txt, inline=False)
        return embed


class DMLockView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(DMLockButton(guild.dms_paused()))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        stato = "🟢 In pausa" if self.guild.dms_paused() else _T("dash2.attivi")
        embed = discord.Embed(
            title=_T("dash.dm_lock2"),
            description=_T("dash.mette_pausa_dm_tra"),
            color=BLU)
        embed.add_field(name=_T("dash.stato"), value=stato, inline=False)
        return embed


class JoinLockView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(JoinLockButton(guild.invites_paused()))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        stato = "🟢 In pausa" if self.guild.invites_paused() else _T("dash2.attivi")
        embed = discord.Embed(
            title=_T("dash.join_lock2"),
            description=_T("dash.mette_pausa_inviti_nessuno"),
            color=BLU)
        embed.add_field(name=_T("dash.stato"), value=stato, inline=False)
        return embed


class ModSectionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=_T("dash.antispam3"), value="antispam", description=_T("dash.protezione_spam_raid_scam")),
            discord.SelectOption(label=_T("dash.jail2"), value="jail", description=_T("dash.sistema_isolamento")),
            discord.SelectOption(label=_T("dash.regole_warn"), value="warn", description=_T("dash.azioni_automatiche_sui_warn")),
            discord.SelectOption(label=_T("dash.autorole2"), value="autorole", description=_T("dash.ruoli_automatici_all_ingresso")),
            discord.SelectOption(label=_T("dash.permessi2"), value="permessi", description=_T("dash.chi_puo_usare_warn")),
            discord.SelectOption(label=_T("staff.section_label"), value="staff", description=_T("staff.section_desc")),
            discord.SelectOption(label=_T("dash.dm_lock2"), value="dmlock", description=_T("dash.pausa_dm_server")),
            discord.SelectOption(label=_T("dash.join_lock2"), value="joinlock", description=_T("dash.pausa_inviti_server")),
        ]
        super().__init__(placeholder=_T("dash.scegli_cosa_configurare"), options=options)

    async def callback(self, interaction: discord.Interaction):
        a, g = self.view.author_id, self.view.guild
        mappa = {
            "antispam": AntispamView, "jail": JailView, "warn": WarnActionsView,
            "autorole": AutoroleView, "permessi": PermissionsView, "staff": StaffView,
            "dmlock": DMLockView, "joinlock": JoinLockView,
        }
        view = mappa[self.values[0]](a, g)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class ModerationView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(ModSectionSelect())
        self.add_item(BackButton("home"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        antispam = _T("dash2.attivo") if config.get("antispam", {}).get("enabled") else _T("dash2.disattivo")
        dm = "🟢 In pausa" if self.guild.dms_paused() else _T("dash2.attivi")
        join = "🟢 In pausa" if self.guild.invites_paused() else _T("dash2.attivi")
        n_regole = len(config.get("warn_actions", []))

        embed = discord.Embed(
            title=_T("dash.moderazione"),
            description=_T("dash.seleziona_cosa_configurare_dal"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato_rapido"), value=(
            f"🚨 Antispam: {antispam}\n" +
            f"🔒 DM Lock: {dm}\n" +
            f"🚪 Join Lock: {join}\n" +
            f"⚠️ Warn rules: {n_regole} active"
        ), inline=False)
        return embed


# ── ANTISPAM ──────────────────────────────────────────────────────────────────
def _antispam_cfg(guild_id):
    config = db.get_log_config(guild_id)
    config.setdefault("antispam", {})
    return config


class ToggleAntispamButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label=_T("dash.antispam"), emoji="🚨",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["enabled"] = not config["antispam"].get("enabled", False)
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ToggleAntiscamButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label=_T("dash.anti_scam_link"), emoji="🎣",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["antiscam"] = not config["antispam"].get("antiscam", False)
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AntispamLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_log_antispam"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["log_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class OpenWhitelistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.whitelist"), emoji="✅", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class OpenCategoriesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.categorie_sanzioni"), emoji="⚙️", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = SpamCategoriesView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AntispamView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        asc = db.get_log_config(guild.id).get("antispam", {})
        self.add_item(ToggleAntispamButton(asc.get("enabled", False)))
        self.add_item(ToggleAntiscamButton(asc.get("antiscam", False)))
        self.add_item(AntispamLogSelect())
        self.add_item(OpenWhitelistButton())
        self.add_item(OpenCategoriesButton())
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        asc = db.get_log_config(self.guild.id).get("antispam", {})
        wl = asc.get("whitelist", {})
        log = f"<#{asc['log_channel']}>" if asc.get("log_channel") else _T("dash2.non_impostato")
        embed = discord.Embed(
            title=_T("dash.antispam3"),
            description=_T("dash.protezione_automatica_contro_spam"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=_T("dash.attivo") if asc.get("enabled") else _T("dash2.disattivo"), inline=True)
        embed.add_field(name=_T("dash.anti_scam"), value=_T("dash.attivo") if asc.get("antiscam") else _T("dash2.disattivo"), inline=True)
        embed.add_field(name=_T("dash.canale_log"), value=log, inline=False)
        embed.add_field(
            name=_T("dash.whitelist2"),
            value=(f"{len(wl.get('channels', []))} channels, " +
                   f"{len(wl.get('roles', []))} roles, " +
                   f"{len(wl.get('users', []))} users"),
            inline=False,
        )
        return embed


# ── WHITELIST ─────────────────────────────────────────────────────────────────
def _dv(ids, tipo):
    return [discord.SelectDefaultValue(id=i, type=tipo) for i in ids]


class WLChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.canali_esenti"), min_values=0, max_values=25, row=0,
                         channel_types=[discord.ChannelType.text, discord.ChannelType.voice],
                         default_values=_dv(ids, discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"].setdefault("whitelist", {})["channels"] = [c.id for c in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class WLRoleSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.ruoli_esenti"), min_values=0, max_values=25, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"].setdefault("whitelist", {})["roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class WLUserSelect(discord.ui.UserSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.utenti_esenti"), min_values=0, max_values=25, row=2,
                         default_values=_dv(ids, discord.SelectDefaultValueType.user))

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"].setdefault("whitelist", {})["users"] = [u.id for u in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class WhitelistView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        wl = db.get_log_config(guild.id).get("antispam", {}).get("whitelist", {})
        self.add_item(WLChannelSelect(wl.get("channels", [])))
        self.add_item(WLRoleSelect(wl.get("roles", [])))
        self.add_item(WLUserSelect(wl.get("users", [])))
        self.add_item(BackButton("antispam"))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=_T("dash.whitelist_antispam"),
            description=_T("dash.canali_ruoli_utenti_esentati"),
            color=BLU,
        )
        return embed


# ── CATEGORIE & SANZIONI ──────────────────────────────────────────────────────
class SpamCategorySelect(discord.ui.Select):
    def __init__(self, config=None):
        options = [discord.SelectOption(label=t(config, lab), value=k) for k, lab in SPAM_CATEGORIES.items()]
        super().__init__(placeholder=_T("dash.scegli_categoria_configurare"), options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = SpamCategoryConfigView(self.view.author_id, self.view.guild, self.values[0])
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SpamCategoriesView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(SpamCategorySelect(db.get_log_config(guild.id)))
        self.add_item(BackButton("antispam"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        righe = []
        for k, lab in SPAM_CATEGORIES.items():
            c = categoria_cfg(config, k)
            stato = "🟢" if c["enabled"] else "🔴"
            sanz = t(config, SANCTIONS.get(c["sanction"], c["sanction"]))
            if c["sanction"] == "timeout" and c["seconds"]:
                sanz += f" {c['seconds'] // 60}min"
            righe.append(f"{stato} **{t(config, lab)}** → {sanz}")
        embed = discord.Embed(title=_T("dash.categorie_sanzioni2"), color=BLU,
                              description="\n".join(righe))
        embed.set_footer(text=_T("dash.scegli_categoria_modificarla"))
        return embed


class ToggleCategoryButton(discord.ui.Button):
    def __init__(self, category, attivo):
        super().__init__(label=_T("dash.attiva_disattiva"), emoji="🔘",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=2)
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        cats = config["antispam"].setdefault("categories", {})
        cur = categoria_cfg(config, self.category)
        cats.setdefault(self.category, {})["enabled"] = not cur["enabled"]
        db.save_log_config(interaction.guild_id, config)
        v = SpamCategoryConfigView(self.view.author_id, self.view.guild, self.category)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SanctionSelect(discord.ui.Select):
    def __init__(self, category, corrente, config=None):
        self.category = category
        options = [discord.SelectOption(label=t(config, lab), value=k, default=(k == corrente))
                   for k, lab in SANCTIONS.items()]
        super().__init__(placeholder=_T("dash.sanzione2"), options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        cats = config["antispam"].setdefault("categories", {})
        cats.setdefault(self.category, {})["sanction"] = self.values[0]
        db.save_log_config(interaction.guild_id, config)
        v = SpamCategoryConfigView(self.view.author_id, self.view.guild, self.category)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SanctionDurationSelect(discord.ui.Select):
    def __init__(self, category, corrente):
        self.category = category
        opzioni = [("10 minuti", 600), ("1 ora", 3600), ("12 ore", 43200), ("1 giorno", 86400)]
        options = [discord.SelectOption(label=lab, value=str(s), default=(s == corrente))
                   for lab, s in opzioni]
        super().__init__(placeholder=_T("dash.durata_timeout"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        cats = config["antispam"].setdefault("categories", {})
        cats.setdefault(self.category, {})["seconds"] = int(self.values[0])
        db.save_log_config(interaction.guild_id, config)
        v = SpamCategoryConfigView(self.view.author_id, self.view.guild, self.category)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SpamCategoryConfigView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, category: str):
        super().__init__(author_id, guild)
        self.category = category
        c = categoria_cfg(db.get_log_config(guild.id), category)
        self.add_item(SanctionSelect(category, c["sanction"], db.get_log_config(guild.id)))
        self.add_item(SanctionDurationSelect(category, c.get("seconds", 600)))
        self.add_item(ToggleCategoryButton(category, c["enabled"]))
        self.add_item(BackButton("categories"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        c = categoria_cfg(config, self.category)
        sanz = t(config, SANCTIONS.get(c["sanction"], c["sanction"]))
        embed = discord.Embed(title="⚙️ " + t(config, SPAM_CATEGORIES[self.category]), color=BLU)
        embed.add_field(name=_T("dash.stato"), value=_T("dash.attiva") if c["enabled"] else _T("dash2.disattiva"), inline=True)
        embed.add_field(name=_T("dash.sanzione"), value=sanz, inline=True)
        if c["sanction"] == "timeout":
            embed.add_field(name=_T("dash.durata"), value=f"{c.get('seconds', 600) // 60} min", inline=True)
        embed.set_footer(text=_T("dash.durata_vale_solo_sanzione"))
        return embed


# ── CONFESSION ────────────────────────────────────────────────────────────────
class ConfessionChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_confessioni2"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        cfg = db.get_config(interaction.guild_id)
        cur_log = cfg["log_channel"] if cfg else None
        db.set_confession_channels(interaction.guild_id, self.values[0].id, cur_log)
        v = ConfessionSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ConfessionLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_log_staff_anti"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        cfg = db.get_config(interaction.guild_id)
        cur_ch = cfg["confession_channel"] if cfg else None
        db.set_confession_channels(interaction.guild_id, cur_ch, self.values[0].id)
        v = ConfessionSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ConfessionSettingsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        feats = db.get_log_config(guild.id).get("features", {})
        self.add_item(FeatureToggleButton("confession", feats.get("confession", True)))
        self.add_item(ConfessionChannelSelect())
        self.add_item(ConfessionLogSelect())
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        cfg = db.get_config(self.guild.id)
        attiva = _T("dash2.attiva") if db.get_log_config(self.guild.id).get("features", {}).get("confession", True) else _T("dash2.disattivata")
        ch = self.guild.get_channel(cfg["confession_channel"]) if cfg and cfg["confession_channel"] else None
        log = self.guild.get_channel(cfg["log_channel"]) if cfg and cfg["log_channel"] else None
        embed = discord.Embed(
            title=_T("dash.confession"),
            description=_T("dash.attiva_disattiva_funzione_imposta"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.canale_confessioni"), value=ch.mention if ch else _T("dash2.non_impostato"), inline=False)
        embed.add_field(name=_T("dash.log_staff"), value=log.mention if log else _T("dash2.non_impostato_opzionale"), inline=False)
        return embed


# ── AUTOROLE ──────────────────────────────────────────────────────────────────
class AutoroleSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.ruoli_assegnare_all_ingresso"),
                         min_values=0, max_values=10, row=0,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config["autoroles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = AutoroleView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoroleView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        ids = db.get_log_config(guild.id).get("autoroles", [])
        self.add_item(AutoroleSelect(ids))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        ids = db.get_log_config(self.guild.id).get("autoroles", [])
        ruoli = [self.guild.get_role(r) for r in ids]
        ruoli = [r.mention for r in ruoli if r]
        embed = discord.Embed(
            title=_T("dash.autorole2"),
            description=_T("dash.ruoli_assegnati_automaticamente_chi"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.ruoli_attivi"), value=" ".join(ruoli) if ruoli else _T("dash2.nessuno"), inline=False)
        return embed


# ── PERMESSI MOD (per categoria: lock / jail / warn) ──────────────────────────
# Valori = CHIAVI: risolte al rendering, non all'import (altrimenti la lingua
# resterebbe congelata a quella di default).
MOD_PERM_CATS = {
    "lock": ("dash2.lock_canali", "lock / unlock"),
    "jail": ("dash2.jail", "dash2.jail_unjail_jailed"),
    "warn": ("dash2.warn", "dash2.warn_warnings_delwarn_clearwarns"),
}


class ModPermSelect(discord.ui.RoleSelect):
    def __init__(self, categoria, label, ids, row):
        super().__init__(placeholder=_T("dash.ruoli_autorizzati_ph", cat=_T(label)),
                         min_values=0, max_values=15, row=row,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))
        self.categoria = categoria

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("mod_perms", {})[self.categoria] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = PermissionsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PermissionsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        perms = db.get_log_config(guild.id).get("mod_perms", {})
        for i, (cat, (label, _)) in enumerate(MOD_PERM_CATS.items()):
            self.add_item(ModPermSelect(cat, label, perms.get(cat, []), i))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        perms = db.get_log_config(self.guild.id).get("mod_perms", {})
        embed = discord.Embed(
            title=_T("dash.permessi_comandi_moderazione"),
            description=(
                _T("dash2.tra_chi_vede_comandi_ha") +
                _T("dash2.possono_davvero_usarli_categoria_n") +
                _T("dash2.amministratori_possono_sempre_se_categoria") +
                _T("dash.vale_permesso_nativo")
            ),
            color=BLU,
        )
        for cat, (label, comandi) in MOD_PERM_CATS.items():
            ids = perms.get(cat, [])
            ruoli = [self.guild.get_role(r) for r in ids]
            ruoli = [r.mention for r in ruoli if r]
            valore = " ".join(ruoli) if ruoli else _T("dash.tutti_chi_lo_vede")
            embed.add_field(name=f"{_T(label)}  ·  `{_T(comandi)}`", value=valore, inline=False)
        return embed


# ── PARTNERSHIP ───────────────────────────────────────────────────────────────
class PartnershipChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_dove_pubblicare_partner"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("partnership", {})["channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = PartnershipSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PartnershipRolesSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.ruoli_possono_fare_partnership"),
                         min_values=0, max_values=15, row=2,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("partnership", {})["roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = PartnershipSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PingConfigButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.configura_ping"), emoji="🔔", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PingConfigModal(self.view))


class PingConfigModal(discord.ui.Modal, title=_T("dash.configura_ping")):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
        ping = db.get_log_config(parent_view.guild.id).get("partnership", {}).get("ping", {})
        self.here = discord.ui.TextInput(
            label=_T("dash.membri_richiesti_pingare_here"), required=False, max_length=10,
            default=str(ping.get("here") or ""), placeholder="es. 500")
        self.everyone = discord.ui.TextInput(
            label=_T("dash.membri_richiesti_pingare_everyone"), required=False, max_length=10,
            default=str(ping.get("everyone") or ""), placeholder=_T("dash.es_1000"))
        self.custom_role = discord.ui.TextInput(
            label=_T("dash.ping_personalizzato_id_ruolo"), required=False, max_length=25,
            default=str(ping.get("custom_role") or ""), placeholder=_T("dash.ph_role_id"))
        self.custom_members = discord.ui.TextInput(
            label=_T("dash.ping_personalizzato_membri_richiesti"), required=False, max_length=10,
            default=str(ping.get("custom_members") or ""), placeholder=_T("dash.ph_member_count"))
        for it in (self.here, self.everyone, self.custom_role, self.custom_members):
            self.add_item(it)

    async def on_submit(self, interaction: discord.Interaction):
        def _int(s):
            s = (s or "").strip()
            return int(s) if s.isdigit() else None
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("partnership", {})["ping"] = {
            "here": _int(self.here.value),
            "everyone": _int(self.everyone.value),
            "custom_role": _int(self.custom_role.value),
            "custom_members": _int(self.custom_members.value),
        }
        db.save_log_config(interaction.guild_id, config)
        v = PartnershipSettingsView(self.parent_view.author_id, self.parent_view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PartnershipSettingsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        p = config.get("partnership", {})
        self.add_item(FeatureToggleButton("partnership", feats.get("partnership", True)))
        self.add_item(PingConfigButton())
        self.add_item(PartnershipChannelSelect())
        self.add_item(PartnershipRolesSelect(p.get("roles", [])))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        p = config.get("partnership", {})
        feats = config.get("features", {})
        attiva = _T("dash2.attiva") if feats.get("partnership", True) else _T("dash2.disattivata")
        ch = self.guild.get_channel(p.get("channel")) if p.get("channel") else None
        roles = [self.guild.get_role(r) for r in p.get("roles", [])]
        roles = [r.mention for r in roles if r]
        ping = p.get("ping", {})
        ping_lines = []
        if ping.get("here"):
            ping_lines.append(f"@here da **{ping['here']}** membri")
        if ping.get("everyone"):
            ping_lines.append(f"@everyone da **{ping['everyone']}** membri")
        if ping.get("custom_role") and ping.get("custom_members"):
            ping_lines.append(f"<@&{ping['custom_role']}> da **{ping['custom_members']}** membri")

        embed = discord.Embed(
            title=_T("dash.partnership"),
            description=(_T("dash2.sistema_partnership_chi_autorizzato_usa") +
                         _T("dash2.pubblicare_partner_nel_canale_dedicato") +
                         _T("dash2.imposta_canale_ruoli_abilitati_ping")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.canale_partner"), value=ch.mention if ch else _T("dash2.non_impostato"), inline=False)
        embed.add_field(name=_T("dash.ruoli_autorizzati"),
                        value=" ".join(roles) if roles else "*nessuno (solo admin)*", inline=False)
        embed.add_field(name=_T("dash.ping"), value="\n".join(ping_lines) if ping_lines else _T("dash2.nessuno"), inline=False)
        return embed


# ── AUTO MESSAGE (messaggi automatici a orario) ───────────────────────────────
def _valida_ora(s, default):
    s = (s or "").strip()
    try:
        h, m = s.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except (ValueError, AttributeError):
        pass
    return default


def _automsg_get(config, msg_id):
    for m in config.get("automsg", {}).get("messages", []):
        if m.get("id") == msg_id:
            return m
    return None


class AutoMsgChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_degli_auto_message"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("automsg", {})["channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = AutoMsgView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgModal(discord.ui.Modal):
    def __init__(self, author_id, guild, msg_id=None):
        super().__init__(title=_T("dash.auto_message"))
        self.author_id = author_id
        self.guild = guild
        self.msg_id = msg_id
        ex = (_automsg_get(db.get_log_config(guild.id), msg_id) or {}) if msg_id is not None else {}
        self.titolo = discord.ui.TextInput(label=_T("dash.titolo_ricordartelo"), max_length=100,
                                           default=ex.get("title", ""), placeholder=_T("dash.ph_example_title"))
        self.orario = discord.ui.TextInput(label=_T("dash.orario_hh_mm_ora"), max_length=5,
                                           default=ex.get("time", "08:00"))
        self.messaggio = discord.ui.TextInput(label=_T("dash.messaggio"), style=discord.TextStyle.paragraph,
                                              max_length=1500, default=ex.get("message", ""),
                                              placeholder=_T("dash.ph_example_greet"))
        for it in (self.titolo, self.orario, self.messaggio):
            self.add_item(it)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        msgs = config.setdefault("automsg", {}).setdefault("messages", [])
        ora = _valida_ora(self.orario.value, "08:00")
        titolo = self.titolo.value.strip() or "Senza titolo"
        if self.msg_id is not None:
            m = _automsg_get(config, self.msg_id)
            if m:
                m["title"], m["time"], m["message"] = titolo, ora, self.messaggio.value
        else:
            new_id = max((m.get("id", 0) for m in msgs), default=0) + 1
            msgs.append({"id": new_id, "title": titolo, "time": ora, "message": self.messaggio.value})
        db.save_log_config(interaction.guild_id, config)
        v = AutoMsgView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgAddButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.aggiungi_messaggio"), style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AutoMsgModal(self.view.author_id, self.view.guild))


class AutoMsgManageSelect(discord.ui.Select):
    def __init__(self, messages):
        options = [discord.SelectOption(label=f"{m.get('title', '?')} ({m.get('time', '?')})"[:100],
                                        value=str(m.get("id"))) for m in messages[:25]]
        super().__init__(placeholder=_T("dash.modifica_elimina_messaggio"), options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = AutoMsgEditView(self.view.author_id, self.view.guild, int(self.values[0]))
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgEditButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.modifica"), style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AutoMsgModal(self.view.author_id, self.view.guild, self.view.msg_id))


class AutoMsgDeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.elimina2"), style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        msgs = config.setdefault("automsg", {}).setdefault("messages", [])
        config["automsg"]["messages"] = [m for m in msgs if m.get("id") != self.view.msg_id]
        db.save_log_config(interaction.guild_id, config)
        v = AutoMsgView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.indietro"), emoji="⬅️", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = AutoMsgView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgEditView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, msg_id: int):
        super().__init__(author_id, guild)
        self.msg_id = msg_id
        self.add_item(AutoMsgEditButton())
        self.add_item(AutoMsgDeleteButton())
        self.add_item(AutoMsgBackButton())

    def build_embed(self) -> discord.Embed:
        m = _automsg_get(db.get_log_config(self.guild.id), self.msg_id) or {}
        embed = discord.Embed(title=f"📨 {m.get('title', '?')}", color=BLU)
        embed.add_field(name=_T("dash.orario"), value=m.get("time", "?"), inline=False)
        embed.add_field(name=_T("dash.messaggio2"), value=(m.get("message") or "*vuoto*")[:1000], inline=False)
        return embed


class AutoMsgView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        msgs = config.get("automsg", {}).get("messages", [])
        self.add_item(FeatureToggleButton("automsg", feats.get("automsg", True)))
        self.add_item(AutoMsgAddButton())
        self.add_item(AutoMsgChannelSelect())
        if msgs:
            self.add_item(AutoMsgManageSelect(msgs))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        feats = config.get("features", {})
        am = config.get("automsg", {})
        attiva = _T("dash2.attiva") if feats.get("automsg", True) else _T("dash2.disattivata")
        ch = self.guild.get_channel(am.get("channel")) if am.get("channel") else None
        righe = [f"• **{m.get('title')}** — {m.get('time')}" for m in am.get("messages", [])]
        embed = discord.Embed(
            title=_T("dash.auto_message2"),
            description=(_T("dash2.messaggi_automatici_inviati_orario_fisso") +
                         _T("dash2.aggiungine_quanti_vuoi_ognuno_ha")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.canale3"), value=ch.mention if ch else _T("dash2.non_impostato"), inline=False)
        embed.add_field(name=_T("dash.messaggi"), value="\n".join(righe)[:1000] if righe else _T("dash2.nessuno"), inline=False)
        embed.add_field(name=_T("dash.variabili"), value="`{server}` · `{membercount}`", inline=False)
        return embed


# ── REACTION AUTOMATICHE ──────────────────────────────────────────────────────
def _parse_emojis(testo, guild=None, maxn=5):
    """Estrae fino a maxn emoji. Accetta unicode, <:nome:id> e anche solo il NOME
    (es. 'fuoco' o ':fuoco:') risolvendolo tra le emoji del server."""
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


def _autoreact_get(config, rule_id):
    for r in config.get("autoreact", {}).get("rules", []):
        if r.get("id") == rule_id:
            return r
    return None


def _autoreact_new_id(rules):
    return max((r.get("id", 0) for r in rules if isinstance(r.get("id"), int)), default=0) + 1


def _autoreact_ensure_ids(guild_id):
    """Assegna un id alle regole vecchie che non ce l'hanno (fix 'interaction failed')."""
    config = db.get_log_config(guild_id)
    rules = config.get("autoreact", {}).get("rules", [])
    if not rules:
        return
    nxt = _autoreact_new_id(rules)
    changed = False
    for r in rules:
        if not isinstance(r.get("id"), int):
            r["id"] = nxt
            nxt += 1
            changed = True
    if changed:
        db.save_log_config(guild_id, config)


# — aggiunta regole —
class AutoReactWordModal(discord.ui.Modal, title=_T("dash.reaction_parola")):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.parola = discord.ui.TextInput(label=_T("dash.parola_frase"), max_length=100)
        self.add_item(self.parola)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.parola.value.strip():
            return await interaction.response.send_message(_T("dash2.scrivi_parola"), ephemeral=True)
        config = db.get_log_config(interaction.guild_id)
        rules = config.setdefault("autoreact", {}).setdefault("rules", [])
        rid = _autoreact_new_id(rules)
        rules.append({"id": rid, "type": "word", "trigger": self.parola.value.strip(),
                      "mode": "contains", "emojis": []})
        db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.author_id, self.guild, rid)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoReactUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.scegli_l_utente_reagisce"),
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        rules = config.setdefault("autoreact", {}).setdefault("rules", [])
        rid = _autoreact_new_id(rules)
        rules.append({"id": rid, "type": "mention", "trigger": str(self.values[0].id),
                      "mode": "contains", "emojis": []})
        db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.view.author_id, self.view.guild, rid)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoReactBackButton(discord.ui.Button):
    def __init__(self, row=1):
        super().__init__(label=_T("dash.indietro"), emoji="⬅️", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        v = AutoReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoReactAddUserView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        self.add_item(AutoReactUserSelect())
        self.add_item(AutoReactBackButton())


class AutoReactAddWordButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.parola"), style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AutoReactWordModal(self.view.author_id, self.view.guild))


class AutoReactAddUserButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.utente"), style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = AutoReactAddUserView(self.view.author_id, self.view.guild)
        embed = discord.Embed(title=_T("dash.reaction_utente"),
                              description=_T("dash.scegli_l_utente_bot"), color=BLU)
        await interaction.response.edit_message(embed=embed, view=v)


class AutoReactBlacklistSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.canali_dove_non_reagire"),
                         channel_types=[discord.ChannelType.text, discord.ChannelType.category],
                         min_values=0, max_values=25, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("autoreact", {})["blacklist_channels"] = [c.id for c in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = AutoReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoReactManageSelect(discord.ui.Select):
    def __init__(self, guild, rules, page=0):
        chunk = rules[page * 25:page * 25 + 25]
        tot = max(1, (len(rules) + 24) // 25)
        options = []
        for r in chunk:
            emo = " ".join(r.get("emojis", []))[:20] or "no emoji"
            if r.get("type") == "mention":
                member = guild.get_member(int(r["trigger"])) if str(r.get("trigger", "")).isdigit() else None
                lab = f"@{member.display_name if member else r['trigger']} → {emo}"
            else:
                modo = "esatta" if r.get("mode") == "exact" else "contiene"
                lab = f"'{r.get('trigger')}' ({modo}) → {emo}"
            options.append(discord.SelectOption(label=lab[:100], value=str(r.get("id"))))
        ph = (f"✏️ Edit a reaction — page {page + 1}/{tot}"
              if tot > 1 else _T("dash2.modifica_reaction"))
        super().__init__(placeholder=ph, options=options or [discord.SelectOption(label="—")], row=2)

    async def callback(self, interaction: discord.Interaction):
        v = RuleEditView(self.view.author_id, self.view.guild, int(self.values[0]))
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoReactPageButton(discord.ui.Button):
    def __init__(self, delta, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=3)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        rules = db.get_log_config(v.guild.id).get("autoreact", {}).get("rules", [])
        tot = max(1, (len(rules) + 24) // 25)
        new_page = max(0, min(tot - 1, v.manage_page + self.delta))
        nv = AutoReactView(v.author_id, v.guild, new_page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


# — modifica di una singola regola —
class ServerEmojiSelect(discord.ui.Select):
    def __init__(self, guild, rule, page=0):
        self.rule_id = rule["id"]
        self.page = page
        emojis = guild.emojis
        chunk = emojis[page * 25:page * 25 + 25]
        self._page_strs = {str(e) for e in chunk}
        current = set(rule.get("emojis", []))
        options = [discord.SelectOption(label=e.name[:100], value=str(e), emoji=e, default=str(e) in current)
                   for e in chunk]
        tot = max(1, (len(emojis) + 24) // 25)
        ph = (f"😀 Emoji dal server (max 5) — pag {page + 1}/{tot}"
              if tot > 1 else _T("dash2.scegli_emoji_dal_server_max"))
        super().__init__(placeholder=ph, min_values=0, max_values=min(5, len(options)) or 1,
                         options=options or [discord.SelectOption(label="—")], row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        r = _autoreact_get(config, self.rule_id)
        if r is not None:
            # conserva le emoji scelte in altre pagine / a mano, aggiorna solo questa pagina
            altri = [e for e in r.get("emojis", []) if e not in self._page_strs]
            r["emojis"] = (altri + list(self.values))[:5]
            db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.view.author_id, self.view.guild, self.rule_id, self.page)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class EmojiPageButton(discord.ui.Button):
    def __init__(self, delta, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        tot = max(1, (len(v.guild.emojis) + 24) // 25)
        new_page = max(0, min(tot - 1, v.emoji_page + self.delta))
        nv = RuleEditView(v.author_id, v.guild, v.rule_id, new_page)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class RuleEmojiModal(discord.ui.Modal, title=_T("dash.emoji_scrivi_o_cerca")):
    def __init__(self, author_id, guild, rule_id):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.rule_id = rule_id
        r = _autoreact_get(db.get_log_config(guild.id), rule_id) or {}
        self.emoji = discord.ui.TextInput(
            label=_T("dash.emoji_o_nomi_max"), required=False,
            default=" ".join(r.get("emojis", [])),
            placeholder=_T("dash.nomeemoji_fuoco_custom_123"), max_length=200)
        self.add_item(self.emoji)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        r = _autoreact_get(config, self.rule_id)
        if r is not None:
            r["emojis"] = _parse_emojis(self.emoji.value, self.guild)
            db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.author_id, self.guild, self.rule_id)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RuleEmojiTextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.emoji_mano"), style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RuleEmojiModal(self.view.author_id, self.view.guild, self.view.rule_id))


class RuleWordEditModal(discord.ui.Modal, title=_T("dash.cambia_parola")):
    def __init__(self, author_id, guild, rule_id):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.rule_id = rule_id
        r = _autoreact_get(db.get_log_config(guild.id), rule_id) or {}
        self.parola = discord.ui.TextInput(label=_T("dash.parola_frase"), default=r.get("trigger", ""), max_length=100)
        self.add_item(self.parola)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        r = _autoreact_get(config, self.rule_id)
        if r is not None and self.parola.value.strip():
            r["trigger"] = self.parola.value.strip()
            db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.author_id, self.guild, self.rule_id)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RuleEditWordButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.cambia_parola2"), style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RuleWordEditModal(self.view.author_id, self.view.guild, self.view.rule_id))


class RuleModeButton(discord.ui.Button):
    def __init__(self, rule):
        is_exact = rule.get("mode") == "exact"
        if rule.get("type") == "mention":
            stato = _T("dash2.solo_tag") if is_exact else "ovunque"
        else:
            stato = _T("dash2.solo_parola") if is_exact else "ovunque"
        super().__init__(label=f"🔁 Modalità: {stato}", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        r = _autoreact_get(config, self.view.rule_id)
        if r is not None:
            r["mode"] = "contains" if r.get("mode") == "exact" else "exact"
            db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.view.author_id, self.view.guild, self.view.rule_id)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RuleDeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.elimina2"), style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        rules = config.setdefault("autoreact", {}).setdefault("rules", [])
        config["autoreact"]["rules"] = [r for r in rules if r.get("id") != self.view.rule_id]
        db.save_log_config(interaction.guild_id, config)
        v = AutoReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RuleEditView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, rule_id: int, emoji_page: int = 0):
        super().__init__(author_id, guild)
        self.rule_id = rule_id
        self.emoji_page = emoji_page
        r = _autoreact_get(db.get_log_config(guild.id), rule_id)
        if r is not None:
            if guild.emojis:
                self.add_item(ServerEmojiSelect(guild, r, emoji_page))
                if len(guild.emojis) > 25:
                    self.add_item(EmojiPageButton(-1, "◀ Emoji"))
                    self.add_item(EmojiPageButton(1, "Emoji ▶"))
            self.add_item(RuleEmojiTextButton())
            self.add_item(RuleModeButton(r))
            if r.get("type") == "word":
                self.add_item(RuleEditWordButton())
            self.add_item(RuleDeleteButton())
        self.add_item(AutoReactBackButton(row=3))

    def build_embed(self) -> discord.Embed:
        r = _autoreact_get(db.get_log_config(self.guild.id), self.rule_id) or {}
        emo = " ".join(r.get("emojis", [])) or _T("dash2.nessuna_scegline_dal_menu")
        if r.get("type") == "mention":
            quando = f"when <@{r.get('trigger')}> gets pinged"
        else:
            modo = _T("dash2.solo_parola_esatta") if r.get("mode") == "exact" else _T("dash2.se_parola_contenuta")
            quando = f"parola `{r.get('trigger')}` ({modo})"
        embed = discord.Embed(title=_T("dash.modifica_reaction"), color=BLU,
                              description=f"**Quando:** {quando}\n**Emoji:** {emo}")
        embed.set_footer(text=_T("dash.emoji_dal_menu_server"))
        return embed


class AutoReactView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, manage_page: int = 0):
        super().__init__(author_id, guild)
        self.manage_page = manage_page
        _autoreact_ensure_ids(guild.id)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        ar = config.get("autoreact", {})
        rules = ar.get("rules", [])
        self.add_item(FeatureToggleButton("autoreact", feats.get("autoreact", True)))
        self.add_item(AutoReactAddWordButton())
        self.add_item(AutoReactAddUserButton())
        self.add_item(AutoReactBlacklistSelect(ar.get("blacklist_channels", [])))
        if rules:
            self.add_item(AutoReactManageSelect(guild, rules, manage_page))
            if len(rules) > 25:
                self.add_item(AutoReactPageButton(-1, "◀ Pagina"))
                self.add_item(AutoReactPageButton(1, "Pagina ▶"))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        feats = config.get("features", {})
        ar = config.get("autoreact", {})
        attiva = _T("dash2.attiva") if feats.get("autoreact", True) else _T("dash2.disattivata")
        righe = []
        for r in ar.get("rules", []):
            emo = " ".join(r.get("emojis", [])) or "*no emoji*"
            if r.get("type") == "mention":
                righe.append(f"• <@{r['trigger']}> → {emo}")
            else:
                modo = _T("dash2.solo_parola") if r.get("mode") == "exact" else "se contenuta"
                righe.append(f"• `{r.get('trigger')}` ({modo}) → {emo}")
        embed = discord.Embed(
            title=_T("dash.reaction_automatiche"),
            description=(_T("dash2.bot_reagisce_quando_messaggio_contiene") +
                         _T("dash2.esatta_o_contenuta_o_quando") +
                         _T("dash2.seleziona_regola_dal_menu_modificarla")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.regole"), value="\n".join(righe)[:1000] if righe else _T("dash2.nessuna"), inline=False)
        bl = ar.get("blacklist_channels", [])
        embed.add_field(name=_T("dash.canali_esclusi2"), value=f"{len(bl)} channels" if bl else _T("dash2.nessuno"), inline=False)
        return embed


# ── COUNTING ──────────────────────────────────────────────────────────────────
from cogs.counting import (milestones_of as counting_milestones,
                           parse_milestones as counting_parse_milestones)


def _counting_cfg(guild_id: int):
    config = db.get_log_config(guild_id)
    return config, config.setdefault("counting", {})


class CountingChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, current, config):
        super().__init__(placeholder=t(config, "counting.channel_placeholder"),
                         channel_types=[discord.ChannelType.text],
                         min_values=0, max_values=1, row=1,
                         default_values=_dv([current] if current else [],
                                            discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config, cnt = _counting_cfg(interaction.guild_id)
        cnt["channel"] = self.values[0].id if self.values else None
        db.save_log_config(interaction.guild_id, config)
        v = CountingView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CountingResetToggle(discord.ui.Button):
    def __init__(self, attivo, config):
        super().__init__(label=t(config, "counting.btn_reset_on" if attivo else "counting.btn_reset_off"),
                         emoji="🔁" if attivo else "🗑️",
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        config, cnt = _counting_cfg(interaction.guild_id)
        cnt["reset_on_fail"] = not cnt.get("reset_on_fail", True)
        db.save_log_config(interaction.guild_id, config)
        v = CountingView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CountingReactToggle(discord.ui.Button):
    def __init__(self, attivo, config):
        super().__init__(label=t(config, "counting.btn_react_on" if attivo else "counting.btn_react_off"),
                         style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        config, cnt = _counting_cfg(interaction.guild_id)
        cnt["react_ok"] = not cnt.get("react_ok", True)
        db.save_log_config(interaction.guild_id, config)
        v = CountingView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CountingMilestonesModal(discord.ui.Modal):
    def __init__(self, author_id, guild):
        config = db.get_log_config(guild.id)
        super().__init__(title=t(config, "counting.modal_title"))
        self.author_id = author_id
        self.guild = guild
        cnt = config.get("counting", {})
        attuali = ", ".join(f"{n}: {e}" for n, e in counting_milestones(cnt).items())
        self.box = discord.ui.TextInput(
            label=t(config, "counting.modal_label"), required=False,
            default=attuali, placeholder="100: 💯, 1000: 🔥",
            max_length=200)
        self.add_item(self.box)

    async def on_submit(self, interaction: discord.Interaction):
        config, cnt = _counting_cfg(interaction.guild_id)
        cnt["milestones"] = counting_parse_milestones(self.box.value)
        db.save_log_config(interaction.guild_id, config)
        v = CountingView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CountingMilestonesButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "counting.btn_milestones"), emoji="🏁",
                         style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CountingMilestonesModal(self.view.author_id, self.view.guild))


class CountingResetCountButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "counting.btn_clear"), emoji="🔄",
                         style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        config, cnt = _counting_cfg(interaction.guild_id)
        cnt["current"] = 0
        cnt["last_user"] = None
        cnt["last_message_id"] = None
        db.save_log_config(interaction.guild_id, config)
        v = CountingView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CountingView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        cnt = config.get("counting", {})
        self.add_item(FeatureToggleButton("counting", feats.get("counting", True)))
        self.add_item(CountingChannelSelect(cnt.get("channel"), config))
        self.add_item(CountingResetToggle(cnt.get("reset_on_fail", True), config))
        self.add_item(CountingReactToggle(cnt.get("react_ok", True), config))
        self.add_item(CountingResetCountButton(config))
        self.add_item(CountingMilestonesButton(config))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        cnt = config.get("counting", {})
        attivo = config.get("features", {}).get("counting", True)
        ch = self.guild.get_channel(cnt.get("channel")) if cnt.get("channel") else None
        modo = t(config, "counting.on_fail_reset" if cnt.get("reset_on_fail", True)
                 else "counting.on_fail_delete")
        attuale = cnt.get("current", 0)
        embed = discord.Embed(title=t(config, "counting.title"),
                              description=t(config, "counting.desc"), color=BLU)
        embed.add_field(name=t(config, "common.state"),
                        value=t(config, "common.enabled" if attivo else "common.disabled"), inline=False)
        embed.add_field(name=t(config, "common.channel"),
                        value=ch.mention if ch else t(config, "common.not_set"), inline=False)
        embed.add_field(name=t(config, "counting.current"),
                        value=t(config, "counting.current_value", n=attuale, next=attuale + 1), inline=True)
        embed.add_field(name=t(config, "counting.record"), value=str(cnt.get("record", 0)), inline=True)
        embed.add_field(name=t(config, "counting.on_fail"), value=modo, inline=False)
        embed.add_field(name=t(config, "counting.react_field"),
                        value=t(config, "counting.react_on" if cnt.get("react_ok", True)
                                else "counting.react_off"), inline=False)
        ms = counting_milestones(cnt)
        embed.add_field(
            name=t(config, "counting.milestones"),
            value=" · ".join(t(config, "counting.milestone_entry", emoji=e, n=n)
                             for n, e in ms.items()) if ms else t(config, "counting.milestones_none"),
            inline=False)
        embed.set_footer(text=t(config, "counting.footer"))
        return embed


class PollChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, current, config):
        super().__init__(placeholder=t(config, "poll.channel_ph"),
                         channel_types=[discord.ChannelType.text],
                         min_values=0, max_values=1, row=2,
                         default_values=_dv([current] if current else [],
                                            discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("poll", {})["channel"] = self.values[0].id if self.values else None
        db.save_log_config(interaction.guild_id, config)
        v = PollView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PollPingSelect(discord.ui.RoleSelect):
    def __init__(self, current, config):
        super().__init__(placeholder=t(config, "poll.ping_ph"),
                         min_values=0, max_values=1, row=3,
                         default_values=_dv([current] if current else [],
                                            discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("poll", {})["ping_role"] = self.values[0].id if self.values else None
        db.save_log_config(interaction.guild_id, config)
        v = PollView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PollResetButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "poll.btn_reset"), emoji="🔄",
                         style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("poll", {})["counter"] = 0
        db.save_log_config(interaction.guild_id, config)
        v = PollView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PollRolesSelect(discord.ui.RoleSelect):
    def __init__(self, ids, config):
        super().__init__(placeholder=t(config, "poll.roles_ph"),
                         min_values=0, max_values=15, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("poll", {})["allowed_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = PollView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PollView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        poll = config.get("poll", {})
        self.add_item(FeatureToggleButton("poll", feats.get("poll", True)))
        self.add_item(PollResetButton(config))
        self.add_item(PollRolesSelect(poll.get("allowed_roles", []), config))
        self.add_item(PollChannelSelect(poll.get("channel"), config))
        self.add_item(PollPingSelect(poll.get("ping_role"), config))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        attivo = config.get("features", {}).get("poll", True)
        poll = config.get("poll", {})
        prossimo = poll.get("counter", 0) + 1
        ruoli = poll.get("allowed_roles", [])
        chi = " ".join(f"<@&{r}>" for r in ruoli) if ruoli else t(config, "poll.roles_none")
        embed = discord.Embed(title=t(config, "poll.title"),
                              description=t(config, "poll.desc"), color=BLU)
        embed.add_field(name=t(config, "common.state"),
                        value=t(config, "common.enabled" if attivo else "common.disabled"),
                        inline=False)
        embed.add_field(name=t(config, "poll.roles_field"), value=chi, inline=False)
        ch = self.guild.get_channel(poll.get("channel")) if poll.get("channel") else None
        embed.add_field(name=t(config, "poll.channel_field"),
                        value=ch.mention if ch else t(config, "poll.channel_none"), inline=False)
        ping = poll.get("ping_role")
        embed.add_field(name=t(config, "poll.ping_field"),
                        value=f"<@&{ping}>" if ping else t(config, "poll.ping_none"), inline=False)
        embed.add_field(name=t(config, "poll.counter"), value=f"**{prossimo}**", inline=False)
        return embed


# ── STAFF (PEX / DEPEX) ───────────────────────────────────────────────────────
def _staff_cfg(guild_id: int):
    config = db.get_log_config(guild_id)
    return config, config.setdefault("staff", {})


class StaffChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, current, config):
        super().__init__(placeholder=t(config, "staff.channel_ph"),
                         channel_types=[discord.ChannelType.text],
                         min_values=0, max_values=1, row=1,
                         default_values=_dv([current] if current else [],
                                            discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config, cfg = _staff_cfg(interaction.guild_id)
        cfg["channel"] = self.values[0].id if self.values else None
        db.save_log_config(interaction.guild_id, config)
        v = StaffView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffAllowedSelect(discord.ui.RoleSelect):
    def __init__(self, ids, config):
        super().__init__(placeholder=t(config, "staff.roles_ph"),
                         min_values=0, max_values=15, row=2,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config, cfg = _staff_cfg(interaction.guild_id)
        cfg["allowed_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = StaffView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffLadderSelect(discord.ui.RoleSelect):
    def __init__(self, ids, config):
        super().__init__(placeholder=t(config, "staff.ladder_ph"),
                         min_values=0, max_values=25, row=3,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config, cfg = _staff_cfg(interaction.guild_id)
        cfg["ladder_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = StaffView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffMemberButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "staff.member_btn"),
                         style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        v = StaffMemberView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffAutoButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "staff.auto_btn"),
                         style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        v = StaffAutoView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        config = db.get_log_config(guild.id)
        cfg = config.get("staff", {})
        feats = config.get("features", {})
        self.add_item(FeatureToggleButton("staff", feats.get("staff", True)))
        self.add_item(StaffChannelSelect(cfg.get("channel"), config))
        self.add_item(StaffAllowedSelect(cfg.get("allowed_roles", []), config))
        self.add_item(StaffLadderSelect(cfg.get("ladder_roles", []), config))
        self.add_item(StaffMemberButton(config))
        self.add_item(StaffAutoButton(config))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        cfg = config.get("staff", {})
        attivo = config.get("features", {}).get("staff", True)
        ch = self.guild.get_channel(cfg.get("channel")) if cfg.get("channel") else None
        allowed = cfg.get("allowed_roles", [])
        member = self.guild.get_role(cfg.get("member_role")) if cfg.get("member_role") else None
        embed = discord.Embed(title=t(config, "staff.title"),
                              description=t(config, "staff.desc"), color=BLU)
        embed.add_field(name=t(config, "common.state"),
                        value=t(config, "common.enabled" if attivo else "common.disabled"),
                        inline=False)
        embed.add_field(name=t(config, "staff.channel_field"),
                        value=ch.mention if ch else t(config, "staff.channel_none"), inline=False)
        embed.add_field(name=t(config, "staff.roles_field"),
                        value=" ".join(f"<@&{r}>" for r in allowed) if allowed
                        else t(config, "staff.roles_none"), inline=False)
        ladder = cfg.get("ladder_roles", [])
        embed.add_field(name=t(config, "staff.ladder_field"),
                        value=f"{len(ladder)} 🎭" if ladder else t(config, "none"), inline=True)
        embed.add_field(name=t(config, "staff.member_field"),
                        value=member.mention if member else t(config, "none"), inline=True)
        embed.add_field(name=t(config, "staff.auto_list"),
                        value=str(len(cfg.get("auto_roles", []))), inline=True)
        return embed


class StaffMemberSelect(discord.ui.RoleSelect):
    def __init__(self, current, config):
        super().__init__(placeholder=t(config, "staff.member_ph"),
                         min_values=0, max_values=1, row=0,
                         default_values=_dv([current] if current else [],
                                            discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config, cfg = _staff_cfg(interaction.guild_id)
        cfg["member_role"] = self.values[0].id if self.values else None
        db.save_log_config(interaction.guild_id, config)
        v = StaffMemberView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffMemberView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        cfg = db.get_log_config(guild.id).get("staff", {})
        self.add_item(StaffMemberSelect(cfg.get("member_role"), db.get_log_config(guild.id)))
        self.add_item(BackButton("staff"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        cfg = config.get("staff", {})
        member = self.guild.get_role(cfg.get("member_role")) if cfg.get("member_role") else None
        embed = discord.Embed(title=t(config, "staff.member_title"),
                              description=t(config, "staff.member_desc"), color=BLU)
        embed.add_field(name=t(config, "staff.member_field"),
                        value=member.mention if member else t(config, "none"), inline=False)
        return embed


class StaffAutoRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="1️⃣ Auto-role to give...", min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_role = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class StaffAutoThresholdSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="2️⃣ Threshold: given from this rank up...",
                         min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_threshold = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class StaffAutoAddButton(discord.ui.Button):
    def __init__(self, config):
        super().__init__(label=t(config, "staff.auto_add"), emoji="➕",
                         style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if not v.pending_role or not v.pending_threshold:
            await interaction.response.send_message(
                t(db.get_log_config(interaction.guild_id), "staff.auto_need_both"), ephemeral=True)
            return
        config, cfg = _staff_cfg(interaction.guild_id)
        autos = cfg.setdefault("auto_roles", [])
        autos[:] = [a for a in autos if a.get("role") != v.pending_role]   # niente doppioni
        autos.append({"role": v.pending_role, "threshold": v.pending_threshold})
        db.save_log_config(interaction.guild_id, config)
        nv = StaffAutoView(v.author_id, v.guild)
        await interaction.response.edit_message(embed=nv.build_embed(), view=nv)


class StaffAutoRemoveSelect(discord.ui.Select):
    def __init__(self, autos, guild, config):
        options = []
        for a in autos[:25]:
            role = guild.get_role(a.get("role"))
            options.append(discord.SelectOption(
                label=(role.name if role else str(a.get("role")))[:100], value=str(a.get("role"))))
        super().__init__(placeholder=t(config, "staff.auto_remove_ph"), row=3,
                         options=options or [discord.SelectOption(label="—", value="_")],
                         disabled=not options)

    async def callback(self, interaction: discord.Interaction):
        config, cfg = _staff_cfg(interaction.guild_id)
        cfg["auto_roles"] = [a for a in cfg.get("auto_roles", [])
                             if str(a.get("role")) != self.values[0]]
        db.save_log_config(interaction.guild_id, config)
        v = StaffAutoView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class StaffAutoView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.pending_role = None
        self.pending_threshold = None
        config = db.get_log_config(guild.id)
        autos = config.get("staff", {}).get("auto_roles", [])
        self.add_item(StaffAutoRoleSelect())
        self.add_item(StaffAutoThresholdSelect())
        self.add_item(StaffAutoAddButton(config))
        self.add_item(StaffAutoRemoveSelect(autos, guild, config))
        self.add_item(BackButton("staff"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        autos = config.get("staff", {}).get("auto_roles", [])
        embed = discord.Embed(title=t(config, "staff.auto_title"),
                              description=t(config, "staff.auto_desc"), color=BLU)
        if autos:
            righe = []
            for a in autos:
                role = self.guild.get_role(a.get("role"))
                thr = self.guild.get_role(a.get("threshold"))
                righe.append(t(config, "staff.auto_entry",
                               role=role.mention if role else "?",
                               threshold=thr.mention if thr else "?"))
            valore = "\n".join(righe)
        else:
            valore = t(config, "staff.auto_none")
        embed.add_field(name=t(config, "staff.auto_list"), value=valore, inline=False)
        return embed


def _feature_view(key: str, author_id: int, guild: discord.Guild):
    if key == "staff":
        return StaffView(author_id, guild)
    if key == "poll":
        return PollView(author_id, guild)
    if key == "counting":
        return CountingView(author_id, guild)
    if key == "quote":
        return QuoteSettingsView(author_id, guild)
    if key == "confession":
        return ConfessionSettingsView(author_id, guild)
    if key == "partnership":
        return PartnershipSettingsView(author_id, guild)
    if key == "automsg":
        return AutoMsgView(author_id, guild)
    if key == "autoreact":
        return AutoReactView(author_id, guild)
    if key == "profile":
        return ProfileDashView(author_id, guild)
    return FeatureDetailView(author_id, guild, key)


class FeatureToggleButton(discord.ui.Button):
    def __init__(self, key: str, enabled: bool):
        # Il pulsante mostra l'AZIONE, non lo stato (quello è già nell'embed):
        # "Attiva" verde, "Disattiva" rosso.
        super().__init__(label=_T("dash.disattiva") if enabled else "Attiva",
                         emoji="🔴" if enabled else "🟢",
                         style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success, row=0)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        feats = config.setdefault("features", {})
        feats[self.key] = not feats.get(self.key, True)
        db.save_log_config(interaction.guild_id, config)
        v = _feature_view(self.key, self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class FeatureDetailView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild, key: str):
        super().__init__(author_id, guild)
        self.key = key
        feats = db.get_log_config(guild.id).get("features", {})
        self.add_item(FeatureToggleButton(key, feats.get(key, True)))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        feats = config.get("features", {})
        stato = t(config, "common.enabled" if feats.get(self.key, True) else "common.disabled")
        embed = discord.Embed(title="🔧 " + t(config, FEATURES[self.key]), color=BLU)
        embed.add_field(name=t(config, "common.state"), value=stato, inline=False)
        return embed


class FeatureSelect(discord.ui.Select):
    def __init__(self, config=None):
        options = [discord.SelectOption(label=t(config, lab), value=k) for k, lab in FEATURES.items()]
        super().__init__(placeholder=t(config, "dash.feature_placeholder"), options=options)

    async def callback(self, interaction: discord.Interaction):
        v = _feature_view(self.values[0], self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class FeaturesView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(FeatureSelect(db.get_log_config(guild.id)))
        self.add_item(BackButton("home"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        feats = config.get("features", {})
        righe = [f"{'🟢' if feats.get(k, True) else '🔴'} {t(config, lab)}" for k, lab in FEATURES.items()]
        embed = discord.Embed(
            title=_T("dash.funzioni_bot"),
            description=_T("dash.seleziona_funzione_dal_menu"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value="\n".join(righe), inline=False)
        return embed


# ── PROFILO UTENTE ────────────────────────────────────────────────────────────
def _profile_cfg(guild_id: int):
    config = db.get_log_config(guild_id)
    return config, config.setdefault("profile", {})


class ProfileSectionSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            (_T("dash2.categorie_ruoli"), "rolecats", _T("dash2.categorie_self_role_profile")),
            ("🛡️ Bypass privacy", "bypass", _T("dash2.ruoli_vedono_avatar_banner_quote")),
            ("🔊 Vocali private", "voices", _T("dash2.collega_canale_vocale_utente")),
            ("⭐ Custom reactions", "react", _T("dash2.ruoli_abilitati_numero_max_emoji")),
            (_T("dash2.ruolo_primario"), "primary", _T("dash2.ruolo_speciale_mostrato_nel_profilo")),
        ]
        super().__init__(placeholder=_T("dash.apri_sotto_sezione"), row=1,
                         options=[discord.SelectOption(label=l, value=v, description=d) for l, v, d in opts])

    async def callback(self, interaction: discord.Interaction):
        m = {"rolecats": RoleCategoriesView, "bypass": BypassRolesView,
             "voices": PrivateVoiceView, "react": CustomReactView, "primary": PrimaryRoleView}
        v = m[self.values[0]](self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ProfileDashView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        feats = db.get_log_config(guild.id).get("features", {})
        self.add_item(FeatureToggleButton("profile", feats.get("profile", True)))
        self.add_item(ProfileSectionSelect())
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config, prof = _profile_cfg(self.guild.id)
        attiva = _T("dash2.attiva") if config.get("features", {}).get("profile", True) else _T("dash2.disattivata")
        bypass = prof.get("privacy_bypass_roles", [])
        voices = prof.get("private_voices", {})
        allowed = prof.get("custom_react", {}).get("allowed_roles", [])
        primary = prof.get("primary_roles", {})
        embed = discord.Embed(
            title=_T("dash.profilo_utente"),
            description=_T("dash.comando_profile_qui_gestisci"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"), value=attiva, inline=False)
        embed.add_field(name=_T("dash.bypass_privacy"), value=f"{len(bypass)} roles", inline=True)
        embed.add_field(name=_T("dash.vocali_private"), value=f"{len(voices)} assegnate", inline=True)
        embed.add_field(name=_T("dash.custom_reactions"), value=f"{len(allowed)} roles", inline=True)
        embed.add_field(name=_T("dash.ruoli_primari"), value=f"{len(primary)} assegnati", inline=True)
        embed.set_footer(text=_T("dash.scegli_sotto_sezione_dal"))
        return embed


class BypassRolesSelect(discord.ui.RoleSelect):
    def __init__(self, current):
        super().__init__(placeholder=_T("dash.ruoli_ignorano_privacy_altrui"),
                         min_values=0, max_values=10, row=0)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof["privacy_bypass_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = BypassRolesView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BypassRolesView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        prof = db.get_log_config(guild.id).get("profile", {})
        self.add_item(BypassRolesSelect(prof.get("privacy_bypass_roles", [])))
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        prof = db.get_log_config(self.guild.id).get("profile", {})
        ids = prof.get("privacy_bypass_roles", [])
        testo = " ".join(f"<@&{r}>" for r in ids) if ids else "*Nessuno (solo l'interessato vede)*"
        embed = discord.Embed(
            title=_T("dash.bypass_privacy"),
            description=_T("dash.questi_ruoli_possono_vedere"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.ruoli_abilitati"), value=testo, inline=False)
        return embed


class PrivateVoiceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.1_canale_vocale"), row=0,
                         channel_types=[discord.ChannelType.voice], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_channel = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrivateVoiceUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.2_utente_cui_assegnarla"), row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_user = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrivateVoiceLinkButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.collega"), emoji="🔗", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if not v.pending_channel or not v.pending_user:
            await interaction.response.send_message(
                _T("dash2.scegli_prima_canale_utente"), ephemeral=True)
            return
        config, prof = _profile_cfg(interaction.guild_id)
        voices = prof.setdefault("private_voices", {})
        # un canale → un utente, e un utente → un canale soltanto
        voices = {c: u for c, u in voices.items()
                  if c != str(v.pending_channel) and u != v.pending_user}
        voices[str(v.pending_channel)] = v.pending_user
        prof["private_voices"] = voices
        db.save_log_config(interaction.guild_id, config)
        v.pending_channel = v.pending_user = None
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PrivateVoiceRemoveSelect(discord.ui.Select):
    def __init__(self, guild, voices):
        options = []
        for cid, uid in list(voices.items())[:25]:
            ch = guild.get_channel(int(cid))
            options.append(discord.SelectOption(
                label=(ch.name if ch else f"channel {cid}")[:80], value=str(cid),
                description=f"Assigned to a user ({uid})"))
        super().__init__(placeholder=_T("dash.rimuovi_assegnazione"), row=3,
                         options=options or [discord.SelectOption(label="—", value="_")],
                         disabled=not options)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof.get("private_voices", {}).pop(self.values[0], None)
        db.save_log_config(interaction.guild_id, config)
        v = PrivateVoiceView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PrivateVoiceView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        self.pending_channel = None
        self.pending_user = None
        voices = db.get_log_config(guild.id).get("profile", {}).get("private_voices", {})
        self.add_item(PrivateVoiceChannelSelect())
        self.add_item(PrivateVoiceUserSelect())
        self.add_item(PrivateVoiceLinkButton())
        self.add_item(PrivateVoiceRemoveSelect(guild, voices))
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        voices = db.get_log_config(self.guild.id).get("profile", {}).get("private_voices", {})
        if voices:
            righe = []
            for cid, uid in voices.items():
                ch = self.guild.get_channel(int(cid))
                nome = ch.mention if ch else f"`channel {cid}`"
                righe.append(f"{nome} → <@{uid}>")
            testo = "\n".join(righe)
        else:
            testo = _T("dash2.nessuna_vocale_assegnata")
        embed = discord.Embed(
            title=_T("dash.vocali_private"),
            description=_T("dash.crea_tu_canale_poi"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.assegnazioni"), value=testo, inline=False)
        if self.pending_channel or self.pending_user:
            c = f"<#{self.pending_channel}>" if self.pending_channel else "?"
            u = f"<@{self.pending_user}>" if self.pending_user else "?"
            embed.add_field(name=_T("dash.attesa"), value=f"{c} → {u}", inline=False)
        return embed


class CustomReactRolesSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.ruoli_abilitati_alle_custom"),
                         min_values=0, max_values=25, row=0)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        cr = prof.setdefault("custom_react", {})
        cr["allowed_roles"] = [r.id for r in self.values]
        # Pulizia: chi non è più abilitato perde la sua custom reaction al tag.
        guild = interaction.guild
        for rule in list(config.get("autoreact", {}).get("rules", [])):
            if rule.get("type") != "mention" or rule.get("source") != "profile":
                continue
            uid = rule.get("trigger")
            member = guild.get_member(int(uid)) if str(uid).isdigit() else None
            if member is None or not custom_react_allowed(config, member):
                remove_profile_mention_rule(config, int(uid))
        db.save_log_config(interaction.guild_id, config)
        v = CustomReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CustomReactMaxSelect(discord.ui.Select):
    def __init__(self, current):
        opts = [discord.SelectOption(label=f"{n} emoji", value=str(n), default=(n == current))
                for n in range(1, 6)]
        super().__init__(placeholder=_T("dash.numero_massimo_emoji"), row=1, options=opts)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof.setdefault("custom_react", {})["max"] = int(self.values[0])
        db.save_log_config(interaction.guild_id, config)
        v = CustomReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CustomReactUserPick(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.modifica_reaction_al_tag"),
                         min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        r = ensure_mention_rule(config, self.values[0].id, source="profile")
        db.save_log_config(interaction.guild_id, config)
        v = RuleEditView(self.view.author_id, self.view.guild, r["id"])
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CustomReactView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        cr = db.get_log_config(guild.id).get("profile", {}).get("custom_react", {})
        self.add_item(CustomReactRolesSelect())
        self.add_item(CustomReactMaxSelect(cr.get("max", 3)))
        self.add_item(CustomReactUserPick())
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        cr = db.get_log_config(self.guild.id).get("profile", {}).get("custom_react", {})
        allowed = cr.get("allowed_roles", [])
        testo = " ".join(f"<@&{r}>" for r in allowed) if allowed else "*Nessuno*"
        embed = discord.Embed(
            title=_T("dash.custom_reactions"),
            description=_T("dash.chi_ha_uno_ruoli"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.ruoli_abilitati"), value=testo, inline=False)
        embed.add_field(name=_T("dash.max_emoji_testa"), value=str(cr.get("max", 3)), inline=False)
        return embed


class PrimaryRoleUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.1_utente"), row=0, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_user = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrimaryRoleRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.2_ruolo_primario"), row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_role = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrimaryRoleAssignButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.assegna"), emoji="✅", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if not v.pending_user or not v.pending_role:
            await interaction.response.send_message(
                _T("dash2.scegli_prima_utente_ruolo"), ephemeral=True)
            return
        config, prof = _profile_cfg(interaction.guild_id)
        prof.setdefault("primary_roles", {})[str(v.pending_user)] = v.pending_role
        db.save_log_config(interaction.guild_id, config)
        v.pending_user = v.pending_role = None
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PrimaryRoleRemoveSelect(discord.ui.Select):
    def __init__(self, primary):
        options = [discord.SelectOption(label=f"user {uid}", value=str(uid))
                   for uid in list(primary.keys())[:25]]
        super().__init__(placeholder=_T("dash.rimuovi_assegnazione"), row=3,
                         options=options or [discord.SelectOption(label="—", value="_")],
                         disabled=not options)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof.get("primary_roles", {}).pop(self.values[0], None)
        db.save_log_config(interaction.guild_id, config)
        v = PrimaryRoleView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PrimaryRoleView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        self.pending_user = None
        self.pending_role = None
        primary = db.get_log_config(guild.id).get("profile", {}).get("primary_roles", {})
        self.add_item(PrimaryRoleUserSelect())
        self.add_item(PrimaryRoleRoleSelect())
        self.add_item(PrimaryRoleAssignButton())
        self.add_item(PrimaryRoleRemoveSelect(primary))
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        primary = db.get_log_config(self.guild.id).get("profile", {}).get("primary_roles", {})
        if primary:
            testo = "\n".join(f"<@{uid}> → <@&{rid}>" for uid, rid in primary.items())
        else:
            testo = _T("dash2.nessuna_assegnazione")
        embed = discord.Embed(
            title=_T("dash.ruolo_primario"),
            description=_T("dash.ruolo_speciale_mostrato_cima"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.assegnazioni"), value=testo, inline=False)
        if self.pending_user or self.pending_role:
            u = f"<@{self.pending_user}>" if self.pending_user else "?"
            r = f"<@&{self.pending_role}>" if self.pending_role else "?"
            embed.add_field(name=_T("dash.attesa"), value=f"{u} → {r}", inline=False)
        return embed


# ── CATEGORIE RUOLI (self-role) ───────────────────────────────────────────────
def _dash_emoji(raw):
    if not raw:
        return None
    try:
        return discord.PartialEmoji.from_str(str(raw))
    except Exception:
        return None


def _new_cat_id(prof: dict) -> str:
    seq = prof.get("role_cat_seq", 0) + 1
    prof["role_cat_seq"] = seq
    return str(seq)


class CategoryModal(discord.ui.Modal):
    def __init__(self, author_id, guild, cat_id=None):
        super().__init__(title=_T("dash.categoria_ruoli"))
        self.author_id = author_id
        self.guild = guild
        self.cat_id = cat_id
        cat = {}
        if cat_id:
            cat = db.get_log_config(guild.id).get("profile", {}).get("role_categories", {}).get(cat_id, {})
        self.nome = discord.ui.TextInput(label=_T("dash.nome"), max_length=80,
                                         default=cat.get("name", ""), placeholder=_T("dash.ph_category_example"))
        self.emoji = discord.ui.TextInput(label=_T("dash.emoji_opzionale"), required=False,
                                          max_length=40, default=cat.get("emoji", ""))
        self.add_item(self.nome)
        self.add_item(self.emoji)

    async def on_submit(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        cats = prof.setdefault("role_categories", {})
        cid = self.cat_id or _new_cat_id(prof)
        cat = cats.get(cid, {"single": False, "roles": []})
        cat["name"] = self.nome.value.strip() or "Categoria"
        cat["emoji"] = (self.emoji.value or "").strip()
        cats[cid] = cat
        db.save_log_config(interaction.guild_id, config)
        v = RoleCategoryEditView(self.author_id, self.guild, cid)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class NewCategoryButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.nuova_categoria"), emoji="➕",
                         style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CategoryModal(self.view.author_id, self.view.guild))


class CategoryEditSelect(discord.ui.Select):
    def __init__(self, cats):
        options = [discord.SelectOption(label=c.get("name", "Categoria")[:100], value=cid,
                                        emoji=_dash_emoji(c.get("emoji")),
                                        description=f"{len(c.get('roles', []))} roles")
                   for cid, c in list(cats.items())[:25]]
        super().__init__(placeholder=_T("dash.modifica_categoria"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = RoleCategoryEditView(self.view.author_id, self.view.guild, self.values[0])
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RoleCategoriesView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        cats = db.get_log_config(guild.id).get("profile", {}).get("role_categories", {})
        self.add_item(NewCategoryButton())
        if cats:
            self.add_item(CategoryEditSelect(cats))
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        cats = db.get_log_config(self.guild.id).get("profile", {}).get("role_categories", {})
        if cats:
            righe = [f"{c.get('emoji', '')} **{c.get('name', '—')}** — " +
                     f"{len(c.get('roles', []))} roles " +
                     f"({'singola' if c.get('single') else 'multipla'})"
                     for c in cats.values()]
            testo = "\n".join(righe)
        else:
            testo = _T("dash2.nessuna_categoria_creane")
        embed = discord.Embed(
            title=_T("dash.categorie_ruoli"),
            description=_T("dash.categorie_self_role_utenti"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.categorie"), value=testo, inline=False)
        return embed


class CategoryRolesSelect(discord.ui.RoleSelect):
    def __init__(self, cat_id):
        super().__init__(placeholder=_T("dash.ruoli_questa_categoria"),
                         min_values=0, max_values=25, row=0)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        cat = prof.get("role_categories", {}).get(self.cat_id)
        if cat is not None:
            cat["roles"] = [r.id for r in self.values]
            db.save_log_config(interaction.guild_id, config)
        v = RoleCategoryEditView(self.view.author_id, self.view.guild, self.cat_id)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SingleMultiToggle(discord.ui.Button):
    def __init__(self, cat_id, single):
        super().__init__(label=_T("dash.scelta_singola") if single else "Scelta: multipla",
                         emoji="1️⃣" if single else "🔢",
                         style=discord.ButtonStyle.secondary, row=1)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        cat = prof.get("role_categories", {}).get(self.cat_id)
        if cat is not None:
            cat["single"] = not cat.get("single", False)
            db.save_log_config(interaction.guild_id, config)
        v = RoleCategoryEditView(self.view.author_id, self.view.guild, self.cat_id)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RenameCategoryButton(discord.ui.Button):
    def __init__(self, cat_id):
        super().__init__(label=_T("dash.rinomina"), emoji="✏️",
                         style=discord.ButtonStyle.secondary, row=1)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CategoryModal(self.view.author_id, self.view.guild, self.cat_id))


class DeleteCategoryButton(discord.ui.Button):
    def __init__(self, cat_id):
        super().__init__(label=_T("dash.elimina"), emoji="🗑️",
                         style=discord.ButtonStyle.danger, row=1)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof.get("role_categories", {}).pop(self.cat_id, None)
        db.save_log_config(interaction.guild_id, config)
        v = RoleCategoriesView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RoleCategoryEditView(BaseView):
    def __init__(self, author_id, guild, cat_id):
        super().__init__(author_id, guild)
        self.cat_id = cat_id
        cat = db.get_log_config(guild.id).get("profile", {}).get("role_categories", {}).get(cat_id, {})
        self.add_item(CategoryRolesSelect(cat_id))
        self.add_item(SingleMultiToggle(cat_id, cat.get("single", False)))
        self.add_item(RenameCategoryButton(cat_id))
        self.add_item(DeleteCategoryButton(cat_id))
        self.add_item(BackButton("rolecats"))

    def build_embed(self) -> discord.Embed:
        cat = db.get_log_config(self.guild.id).get("profile", {}).get("role_categories", {}).get(self.cat_id, {})
        roles = cat.get("roles", [])
        testo = " ".join(f"<@&{r}>" for r in roles) if roles else "*Nessuno*"
        embed = discord.Embed(
            title=f"{cat.get('emoji', '')} {cat.get('name', 'Category')}".strip(),
            description=_T("dash.scegli_ruoli_tipo_scelta"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.tipo"),
                        value=_T("dash.scelta_singola_solo_ruolo") if cat.get("single")
                        else _T("dash2.scelta_multipla_piu_ruoli"), inline=False)
        embed.add_field(name=_T("dash.ruoli"), value=testo, inline=False)
        return embed


# ── LIVELLI ───────────────────────────────────────────────────────────────────
class LevelToggleButton(discord.ui.Button):
    def __init__(self, key, label, on, row):
        super().__init__(label=label, emoji="🟢" if on else "🔴",
                         style=discord.ButtonStyle.success if on else discord.ButtonStyle.danger, row=row)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        c = ls.cfg(config)
        config.setdefault("levels", {})[self.key] = not c[self.key]
        db.save_log_config(interaction.guild_id, config)
        v = LevelsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpCooldownModal(discord.ui.Modal, title=_T("dash.xp_cooldown")):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        c = ls.cfg(db.get_log_config(guild.id))
        self.xp_msg = discord.ui.TextInput(label=_T("dash.xp_messaggio"), default=str(c["xp_message"]), max_length=6)
        self.voice_xp = discord.ui.TextInput(label=_T("dash.xp_intervallo_vocale"), default=str(c["voice_xp"]), max_length=6)
        self.cd_text = discord.ui.TextInput(label=_T("dash.cooldown_chat_es_60s"),
                                            default=ls.fmt_duration(c["cooldown_text"]), max_length=8)
        self.cd_voice = discord.ui.TextInput(label=_T("dash.cooldown_vocale_es_1m"),
                                             default=ls.fmt_duration(c["cooldown_voice"]), max_length=8)
        for it in (self.xp_msg, self.voice_xp, self.cd_text, self.cd_voice):
            self.add_item(it)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        c = ls.cfg(config)
        lv = config.setdefault("levels", {})

        def _i(s, d):
            s = (s or "").strip()
            return max(0, int(s)) if s.isdigit() else d
        lv["xp_message"] = _i(self.xp_msg.value, c["xp_message"])
        lv["voice_xp"] = _i(self.voice_xp.value, c["voice_xp"])
        ct = ls.parse_duration(self.cd_text.value)
        cv = ls.parse_duration(self.cd_voice.value)
        lv["cooldown_text"] = ct if ct is not None else c["cooldown_text"]
        lv["cooldown_voice"] = cv if cv is not None else c["cooldown_voice"]
        db.save_log_config(interaction.guild_id, config)
        v = LevelsView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpCooldownButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.xp_cooldown2"), style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(XpCooldownModal(self.view.author_id, self.view.guild))


class LevelSectionSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            ("📈 Curva XP", "curva", _T("dash2.base_incremento_override_livello")),
            ("🎉 Level-up", "levelup", _T("dash2.canale_messaggio_salita_livello")),
            (_T("dash2.ruoli_premio"), "rewards", _T("dash2.assegna_ruoli_certi_livelli")),
            ("✨ Multiplier", "multiplier", _T("dash2.ruoli_danno_xp_extra")),
            ("🚫 Blacklist", "blacklist", _T("dash2.ruoli_utenti_esclusi_dagli_xp")),
        ]
        super().__init__(placeholder=_T("dash.apri_sotto_sezione"), row=0,
                         options=[discord.SelectOption(label=l, value=v, description=d) for l, v, d in opts])

    async def callback(self, interaction: discord.Interaction):
        mapping = {"curva": LevelCurveView, "levelup": LevelUpView, "rewards": LevelRewardsView,
                   "multiplier": LevelMultiplierView, "blacklist": LevelBlacklistView}
        v = mapping[self.values[0]](self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        c = ls.cfg(db.get_log_config(guild.id))
        self.add_item(LevelSectionSelect())
        self.add_item(LevelToggleButton("enabled", "Sistema", c["enabled"], 1))
        self.add_item(LevelToggleButton("text_enabled", "XP chat", c["text_enabled"], 1))
        self.add_item(LevelToggleButton("voice_enabled", "XP vocale", c["voice_enabled"], 1))
        self.add_item(XpCooldownButton())
        self.add_item(LevelToggleButton("coleave", "Coleave", c["coleave"], 3))
        self.add_item(LevelToggleButton("reward_replace", "Reward replace", c["reward_replace"], 3))
        self.add_item(BackButton("home"))

    def build_embed(self) -> discord.Embed:
        c = ls.cfg(db.get_log_config(self.guild.id))
        sn = lambda b: "🟢" if b else "🔴"
        embed = discord.Embed(
            title=_T("dash.livelli"),
            description=(_T("dash2.sistema_xp_livelli_usa_menu") +
                         _T("dash2.pulsanti_attivare_disattivare_impostare_xp") +
                         _T("dash2.coleave_azzera_xp_quando_utente") +
                         _T("dash2.reward_replace_sostituisce_ruoli_premio")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.stato"),
                        value=f"{sn(c['enabled'])} Sistema · {sn(c['text_enabled'])} Chat · {sn(c['voice_enabled'])} Vocale",
                        inline=False)
        embed.add_field(name=_T("dash.xp_messaggio"), value=f"{c['xp_message']}", inline=True)
        embed.add_field(name=_T("dash.xp_vocale"), value=f"{c['voice_xp']}", inline=True)
        embed.add_field(name=_T("dash.cooldown"),
                        value=f"chat {ls.fmt_duration(c['cooldown_text'])} · voce {ls.fmt_duration(c['cooldown_voice'])}",
                        inline=True)
        embed.add_field(name=_T("dash.coleave"), value=sn(c["coleave"]), inline=True)
        embed.add_field(name=_T("dash.reward_replace"), value=sn(c["reward_replace"]), inline=True)
        return embed


# — Curva XP (manuale) —
class CurveAddModal(discord.ui.Modal, title=_T("dash.aggiungi_livello")):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.livello = discord.ui.TextInput(label=_T("dash.livello"), placeholder=_T("dash.es_1"), max_length=4)
        self.xp = discord.ui.TextInput(label=_T("dash.xp_salire_al_livello"),
                                       placeholder=_T("dash.es_1000"), max_length=9)
        self.add_item(self.livello)
        self.add_item(self.xp)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        curve = config.setdefault("levels", {}).setdefault("curve", {})
        if self.livello.value.strip().isdigit() and self.xp.value.strip().isdigit():
            curve[self.livello.value.strip()] = int(self.xp.value.strip())
            db.save_log_config(interaction.guild_id, config)
        v = LevelCurveView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CurveAddButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.aggiungi_modifica_livello"), style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CurveAddModal(self.view.author_id, self.view.guild))


class CurveBulkModal(discord.ui.Modal, title=_T("dash.import_curva_blocco")):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.testo = discord.ui.TextInput(
            label=_T("dash.xp_livello_ordine_dal"),
            style=discord.TextStyle.paragraph, max_length=4000,
            placeholder=_T("dash.46_64_84_106"))
        self.add_item(self.testo)

    async def on_submit(self, interaction: discord.Interaction):
        nums = []
        for tok in self.testo.value.replace(",", " ").replace(";", " ").split():
            t = tok.strip()
            if t.isdigit():
                nums.append(int(t))
        if nums:
            curve = {str(i): n for i, n in enumerate(nums) if n > 0}
            config = db.get_log_config(interaction.guild_id)
            config.setdefault("levels", {})["curve"] = curve
            db.save_log_config(interaction.guild_id, config)
        v = LevelCurveView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CurveBulkButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.import_blocco"), style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CurveBulkModal(self.view.author_id, self.view.guild))


class CurveClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.svuota_curva"), style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["curve"] = {}
        db.save_log_config(interaction.guild_id, config)
        v = LevelCurveView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CurveRemoveSelect(discord.ui.Select):
    def __init__(self, curve):
        options = []
        for lvl, xp in sorted(curve.items(), key=lambda x: int(x[0]))[:25]:
            options.append(discord.SelectOption(label=f"Level {lvl} → {xp} XP"[:100], value=str(lvl)))
        super().__init__(placeholder=_T("dash.rimuovi_livello"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {}).setdefault("curve", {}).pop(self.values[0], None)
        db.save_log_config(interaction.guild_id, config)
        v = LevelCurveView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelCurveView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        curve = ls.cfg(db.get_log_config(guild.id)).get("curve", {})
        self.add_item(CurveAddButton())
        self.add_item(CurveBulkButton())
        if curve:
            self.add_item(CurveRemoveSelect(curve))
            self.add_item(CurveClearButton())
        self.add_item(BackButton("levels"))

    def build_embed(self) -> discord.Embed:
        curve = ls.cfg(db.get_log_config(self.guild.id)).get("curve", {})
        items = sorted(curve.items(), key=lambda x: int(x[0]))
        if not items:
            testo = _T("dash2.nessun_livello_impostato_default_100")
        elif len(items) <= 12:
            testo = "\n".join(f"**Lv {lvl}** → `{xp}` XP per salire" for lvl, xp in items)
        else:
            head = "\n".join(f"**Lv {lvl}** → `{xp}`" for lvl, xp in items[:8])
            testo = f"{head}\n… and **{len(items) - 8}** more levels set"
        embed = discord.Embed(
            title=_T("dash.curva_xp_manuale"),
            description=(_T("dash2.imposti_tu_livello_livello_quanti") +
                         _T("dash2.import_blocco_incolli_tutti_valori") +
                         _T("dash2.livelli_senza_valore_usano_quello")),
            color=BLU,
        )
        embed.add_field(name=f"Levels set ({len(items)})", value=testo, inline=False)
        return embed


# — Level-up (canale + messaggio) —
class LevelUpChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.canale_messaggi_level_up"),
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["levelup_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = LevelUpView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelUpResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.usa_canale_messaggio"), emoji="♻️", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["levelup_channel"] = None
        db.save_log_config(interaction.guild_id, config)
        v = LevelUpView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelUpMessageModal(discord.ui.Modal, title=_T("dash.embed_level_up")):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        c = ls.cfg(db.get_log_config(guild.id))
        self.titolo = discord.ui.TextInput(
            label=_T("dash.titolo"), max_length=256, required=False,
            default=c["levelup_title"], placeholder="{user_name} leveled up!")
        self.msg = discord.ui.TextInput(
            label=_T("dash.testo"), style=discord.TextStyle.paragraph, max_length=1500, required=False,
            default=c["levelup_message"], placeholder=_T("dash.ph_levelup_msg"))
        self.colore = discord.ui.TextInput(
            label=_T("dash.colore_embed_hex_vuoto"), max_length=7, required=False,
            default=c["levelup_color"], placeholder=_T("dash.es_f1c40f"))
        self.add_item(self.titolo)
        self.add_item(self.msg)
        self.add_item(self.colore)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        lv = config.setdefault("levels", {})
        lv["levelup_title"] = self.titolo.value
        lv["levelup_message"] = self.msg.value
        lv["levelup_color"] = self.colore.value.strip().lstrip("#")
        db.save_log_config(interaction.guild_id, config)
        v = LevelUpView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelUpMessageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=_T("dash.titolo_testo"), style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LevelUpMessageModal(self.view.author_id, self.view.guild))


class LevelUpView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(LevelUpChannelSelect())
        self.add_item(LevelUpResetButton())
        self.add_item(LevelUpMessageButton())
        self.add_item(BackButton("levels"))

    def build_embed(self) -> discord.Embed:
        c = ls.cfg(db.get_log_config(self.guild.id))
        ch = self.guild.get_channel(c["levelup_channel"]) if c["levelup_channel"] else None
        dove = ch.mention if ch else _T("dash2.nel_canale_dove_l_utente")
        embed = discord.Embed(
            title=_T("dash.embed_level_up2"),
            description=(_T("dash2.embed_inviato_quando_utente_sale") +
                         "**Variabili:** `{user}` `{user_name}` `{level}` `{server}`"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.canale2"), value=dove, inline=False)
        embed.add_field(name=_T("dash.titolo2"), value=f"```{(c['levelup_title'] or '—')[:250]}```", inline=False)
        embed.add_field(name=_T("dash.testo2"), value=f"```{(c['levelup_message'] or '—')[:500]}```", inline=False)
        embed.add_field(name=_T("dash.colore"), value=f"`#{c['levelup_color']}`" if c['levelup_color'] else "Automatic (role colour)", inline=False)
        return embed


# — Ruoli premio —
class RewardLevelModal(discord.ui.Modal, title=_T("dash.ruolo_premio")):
    def __init__(self, author_id, guild, role):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.role = role
        self.livello = discord.ui.TextInput(label=f"Level for {role.name}", placeholder="es. 10", max_length=4)
        self.add_item(self.livello)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        rewards = config.setdefault("levels", {}).setdefault("rewards", {})
        if self.livello.value.strip().isdigit():
            rewards[self.livello.value.strip()] = self.role.id
            db.save_log_config(interaction.guild_id, config)
        v = LevelRewardsView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class RewardRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.scegli_ruolo_assegnare_livello"),
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RewardLevelModal(self.view.author_id, self.view.guild, self.values[0]))


class RewardRemoveSelect(discord.ui.Select):
    def __init__(self, guild, rewards):
        options = []
        for lvl, rid in sorted(rewards.items(), key=lambda x: int(x[0])):
            role = guild.get_role(rid)
            nome = role.name if role else f"role {rid}"
            options.append(discord.SelectOption(label=f"Level {lvl} → {nome}"[:100], value=str(lvl)))
        super().__init__(placeholder=_T("dash.rimuovi_premio"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {}).setdefault("rewards", {}).pop(self.values[0], None)
        db.save_log_config(interaction.guild_id, config)
        v = LevelRewardsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelRewardsView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        rewards = ls.cfg(db.get_log_config(guild.id)).get("rewards", {})
        self.add_item(RewardRoleSelect())
        if rewards:
            self.add_item(RewardRemoveSelect(guild, rewards))
        self.add_item(BackButton("levels"))

    def build_embed(self) -> discord.Embed:
        c = ls.cfg(db.get_log_config(self.guild.id))
        rewards = c.get("rewards", {})
        if rewards:
            righe = []
            for lvl, rid in sorted(rewards.items(), key=lambda x: int(x[0])):
                righe.append(f"**Lv {lvl}** → <@&{rid}>")
            testo = "\n".join(righe)
        else:
            testo = _T("dash2.nessun_premio_impostato")
        embed = discord.Embed(
            title=_T("dash.ruoli_premio"),
            description=(_T("dash2.assegna_ruolo_al_raggiungimento_livello") +
                         f"**Reward replace:** {'🟢 sostituisce' if c['reward_replace'] else '🔴 accumula'} " +
                         _T("dash2.modificabile_dalla_pagina_livelli")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.premi"), value=testo, inline=False)
        return embed


# — Multiplier —
class MultiplierValueModal(discord.ui.Modal, title=_T("dash.multiplier_ruolo")):
    def __init__(self, author_id, guild, role):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.role = role
        self.valore = discord.ui.TextInput(label=f"Multiplier for {role.name}", placeholder="es. 2 o 1.5",
                                           max_length=6)
        self.add_item(self.valore)

    async def on_submit(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        mult = config.setdefault("levels", {}).setdefault("multipliers", {})
        try:
            v = float(self.valore.value.replace(",", "."))
            mult[str(self.role.id)] = v
            db.save_log_config(interaction.guild_id, config)
        except ValueError:
            pass
        view = LevelMultiplierView(self.author_id, self.guild)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class MultiplierRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder=_T("dash.scegli_ruolo_cui_dare"),
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            MultiplierValueModal(self.view.author_id, self.view.guild, self.values[0]))


class MultiplierRemoveSelect(discord.ui.Select):
    def __init__(self, guild, mult):
        options = []
        for rid, val in mult.items():
            role = guild.get_role(int(rid))
            nome = role.name if role else f"role {rid}"
            options.append(discord.SelectOption(label=f"{nome} ×{val}"[:100], value=str(rid)))
        super().__init__(placeholder=_T("dash.rimuovi_multiplier"), options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {}).setdefault("multipliers", {}).pop(self.values[0], None)
        db.save_log_config(interaction.guild_id, config)
        v = LevelMultiplierView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelMultiplierView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        mult = ls.cfg(db.get_log_config(guild.id)).get("multipliers", {})
        self.add_item(MultiplierRoleSelect())
        if mult:
            self.add_item(MultiplierRemoveSelect(guild, mult))
        self.add_item(BackButton("levels"))

    def build_embed(self) -> discord.Embed:
        mult = ls.cfg(db.get_log_config(self.guild.id)).get("multipliers", {})
        if mult:
            testo = "\n".join(f"<@&{rid}> → **×{val}**" for rid, val in mult.items())
        else:
            testo = _T("dash2.nessun_multiplier")
        embed = discord.Embed(
            title=_T("dash.multiplier"),
            description=_T("dash.ruoli_danno_xp_extra"),
            color=BLU,
        )
        embed.add_field(name=_T("dash.multiplier_attivi"), value=testo, inline=False)
        return embed


# — Blacklist XP —
class XpBlacklistRolesSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.ruoli_esclusi_dagli_xp"), min_values=0, max_values=25, row=0,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["blacklist_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LevelBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpBlacklistUsersSelect(discord.ui.UserSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.utenti_esclusi_dagli_xp"), min_values=0, max_values=25, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.user))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["blacklist_users"] = [u.id for u in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LevelBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpBlacklistChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder=_T("dash.canali_esclusi_dagli_xp"),
                         channel_types=[discord.ChannelType.text, discord.ChannelType.voice,
                                        discord.ChannelType.category],
                         min_values=0, max_values=25, row=2,
                         default_values=_dv(ids, discord.SelectDefaultValueType.channel))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["blacklist_channels"] = [ch.id for ch in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LevelBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelBlacklistView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        c = ls.cfg(db.get_log_config(guild.id))
        self.add_item(XpBlacklistRolesSelect(c.get("blacklist_roles", [])))
        self.add_item(XpBlacklistUsersSelect(c.get("blacklist_users", [])))
        self.add_item(XpBlacklistChannelsSelect(c.get("blacklist_channels", [])))
        self.add_item(BackButton("levels"))

    def build_embed(self) -> discord.Embed:
        c = ls.cfg(db.get_log_config(self.guild.id))
        embed = discord.Embed(
            title=_T("dash.blacklist_xp"),
            description=(_T("dash2.ruoli_utenti_canali_non_danno") +
                         "Seleziona quelli desiderati nei menu (la selezione sostituisce la lista).\n" +
                         _T("dash2.canali_puoi_scegliere_anche_categoria")),
            color=BLU,
        )
        embed.add_field(name=_T("dash.ruoli_esclusi"),
                        value=f"{len(c.get('blacklist_roles', []))} roles" if c.get("blacklist_roles") else _T("dash2.nessuno"),
                        inline=True)
        embed.add_field(name=_T("dash.utenti_esclusi"),
                        value=f"{len(c.get('blacklist_users', []))} users" if c.get("blacklist_users") else _T("dash2.nessuno"),
                        inline=True)
        embed.add_field(name=_T("dash.canali_esclusi"),
                        value=f"{len(c.get('blacklist_channels', []))} channels" if c.get("blacklist_channels") else _T("dash2.nessuno"),
                        inline=True)
        return embed


# ── COG ───────────────────────────────────────────────────────────────────────
class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dashboard", description="Open the server configuration panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def dashboard(self, interaction: discord.Interaction):
        view = DashboardView(interaction.user.id, interaction.guild)
        embed = build_main_embed(interaction.guild, db.get_log_config(interaction.guild_id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Dashboard(bot))
