import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db
import levelsystem as ls
from logconfig import LOG_CATEGORIES, FEATURES, SPAM_CATEGORIES, SANCTIONS, categoria_cfg

BLU = 0x5865F2


def build_main_embed(guild: discord.Guild, config: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⚙️ Dashboard di configurazione",
        description="Seleziona una sezione dal menu qui sotto per configurarla.",
        color=BLU,
    )
    embed.add_field(
        name="Sezioni disponibili",
        value=(
            "📋 **Log** — canali ed eventi di log\n"
            "🔧 **Funzioni** — attiva/disattiva le funzioni del bot\n"
            "🛡️ **Moderazione** — regole automatiche dei warn\n"
            "📊 **Livelli** — sistema XP, premi, classifica"
        ),
        inline=False,
    )
    embed.set_footer(text="Le modifiche vengono salvate automaticamente")
    return embed


# ── COMPONENTI ────────────────────────────────────────────────────────────────
class BackButton(discord.ui.Button):
    def __init__(self, destination: str = "home"):
        super().__init__(label="Indietro", emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
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
        else:
            view = DashboardView(self.view.author_id, self.view.guild)
            embed = build_main_embed(self.view.guild, db.get_log_config(self.view.guild.id))
        await interaction.response.edit_message(embed=embed, view=view)


class HomeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📋 Log", value="logs",
                                 description="Configura i canali e gli eventi di log"),
            discord.SelectOption(label="🔧 Funzioni", value="features",
                                 description="Attiva o disattiva le funzioni del bot"),
            discord.SelectOption(label="🛡️ Moderazione", value="mod",
                                 description="Antispam, jail, warn, lock, autorole, permessi"),
            discord.SelectOption(label="📊 Livelli", value="levels",
                                 description="Sistema XP, premi, multiplier, classifica"),
        ]
        super().__init__(placeholder="Scegli una sezione...", options=options)

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
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=key)
            for key, (label, _) in LOG_CATEGORIES.items()
        ]
        super().__init__(placeholder="📋 Scegli una categoria di log...", options=options)

    async def callback(self, interaction: discord.Interaction):
        view = CategoryView(self.view.author_id, self.view.guild, self.values[0])
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, category: str):
        super().__init__(
            placeholder="📂 Scegli il canale di log per questa categoria...",
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
            discord.SelectOption(label=elabel, value=ek, default=enabled.get(ek, False))
            for ek, elabel in events.items()
        ]
        super().__init__(
            placeholder="✅ Scegli gli eventi da registrare...",
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
            placeholder="📂 Scegli il canale dove pubblicare le quote...",
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
        super().__init__(label="Usa il canale del comando", emoji="♻️",
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
        super().__init__(placeholder="1️⃣ Numero di warn...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_count = int(self.values[0])
        await self.view.refresh(interaction)


class WarnActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Timeout 10 minuti", value="timeout:600"),
            discord.SelectOption(label="Timeout 1 ora", value="timeout:3600"),
            discord.SelectOption(label="Timeout 12 ore", value="timeout:43200"),
            discord.SelectOption(label="Timeout 1 giorno", value="timeout:86400"),
            discord.SelectOption(label="Kick", value="kick:0"),
            discord.SelectOption(label="Ban", value="ban:0"),
        ]
        super().__init__(placeholder="2️⃣ Azione da applicare...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        azione, secondi = self.values[0].split(":")
        self.view.pending_action = azione
        self.view.pending_seconds = int(secondi)
        await self.view.refresh(interaction)


class AddRuleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Aggiungi regola", emoji="➕", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if v.pending_count is None or v.pending_action is None:
            await interaction.response.send_message(
                "❌ Scegli prima il numero di warn e l'azione.", ephemeral=True)
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
        super().__init__(placeholder="🗑️ Rimuovi una regola...", options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        config = db.get_log_config(interaction.guild_id)
        config["warn_actions"] = [r for r in config.get("warn_actions", []) if r["count"] != count]
        db.save_log_config(interaction.guild_id, config)
        new_view = WarnActionsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)


# ── VIEW ──────────────────────────────────────────────────────────────────────
class BaseView(discord.ui.View):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild = guild

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo chi ha aperto la dashboard può usarla.", ephemeral=True
            )
            return False
        return True


class DashboardView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(HomeSelect())


class OpenLogBlacklistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Canali blacklist", emoji="📵", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BlacklistChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Canali esclusi dai log (testuali + vocali)...",
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
        super().__init__(placeholder="🕵️ Canale segreto dove mandare quei log (opzionale)...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("log_blacklist", {})["secret_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = LogBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class BlacklistSecretResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ignora invece di redirigere", emoji="🚫",
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
            title="📵 Canali blacklist (log)",
            description=("I log dei canali selezionati **non** finiscono nei log normali.\n"
                         "Se imposti un **canale segreto**, vengono rediretti lì; altrimenti vengono **ignorati**."),
            color=BLU,
        )
        embed.add_field(name="Canali esclusi", value=f"{len(chans)} canali" if chans else "*nessuno*", inline=False)
        embed.add_field(name="🕵️ Canale segreto",
                        value=f"<#{secret}>" if secret else "Nessuno (i log vengono ignorati)", inline=False)
        return embed


class LogsMenuView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(LogCategorySelect())
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
                stato = f"<#{ch}> • {attivi}/{len(events)} eventi attivi"
            else:
                stato = "❌ non configurato"
            righe.append(f"**{label}** — {stato}")
        embed = discord.Embed(
            title="📋 Log",
            description="Scegli una categoria dal menu per configurarla.",
            color=BLU,
        )
        embed.add_field(name="Categorie", value="\n".join(righe), inline=False)
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
            f"{'🟢' if eventi_cfg.get(ek, False) else '🔴'} {elabel}"
            for ek, elabel in events.items()
        ]
        embed = discord.Embed(title=f"Configura {label} Log", color=BLU)
        embed.add_field(name="📂 Canale", value=f"<#{ch}>" if ch else "❌ nessuno", inline=False)
        embed.add_field(name="Eventi", value="\n".join(righe), inline=False)
        embed.set_footer(text="Scegli il canale e spunta gli eventi da registrare")
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
        attiva = "🟢 Attiva" if config.get("features", {}).get("quote", True) else "🔴 Disattivata"
        cid = config.get("quote_channel")
        dove = f"<#{cid}> (canale fisso)" if cid else "Nel canale dove viene usato il comando"
        embed = discord.Embed(
            title="💬 Quote",
            description="Attiva/disattiva la funzione e scegli dove pubblicare le citazioni.",
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="📍 Destinazione", value=dove, inline=False)
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
            testo = "*Nessuna regola impostata.*"

        embed = discord.Embed(
            title="⚠️ Regole automatiche Warn",
            description="Imposta un'azione automatica al raggiungimento di un certo numero di warn.",
            color=BLU,
        )
        embed.add_field(name="Regole attive", value=testo, inline=False)
        if self.pending_count is not None or self.pending_action is not None:
            c = self.pending_count if self.pending_count is not None else "?"
            a = _desc_azione(self.pending_action, self.pending_seconds) if self.pending_action else "?"
            embed.add_field(name="✏️ Nuova regola", value=f"{c} warn → {a}", inline=False)
        embed.set_footer(text="Scegli numero + azione, poi premi Aggiungi regola")
        return embed

    async def refresh(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class DMLockButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label="DM Lock", emoji="🔒",
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
        super().__init__(label="Join Lock", emoji="🚪",
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
        super().__init__(label="Setup", emoji="🛠️", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = db.get_log_config(guild.id)
        jc = config.get("jail", {})
        role = guild.get_role(jc.get("role")) if jc.get("role") else None
        channel = guild.get_channel(jc.get("channel")) if jc.get("channel") else None

        if role and channel:
            await interaction.response.send_message(
                "✅ Il Jail è già configurato. Usa **Aggiorna canali** se hai aggiunto canali nuovi.",
                ephemeral=True)
            return

        await interaction.response.defer()
        try:
            if not role:
                role = await guild.create_role(name="Jailed", colour=discord.Colour.dark_grey(),
                                               reason="Setup Jail")
            if not channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                      read_message_history=True),
                }
                channel = await guild.create_text_channel("jail", overwrites=overwrites, reason="Setup Jail")

            for ch in guild.channels:
                if ch.id == channel.id:
                    continue
                try:
                    await ch.set_permissions(role, view_channel=False, reason="Setup Jail")
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
        super().__init__(label="Aggiorna canali", emoji="🔄", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = db.get_log_config(guild.id)
        jc = config.get("jail", {})
        role = guild.get_role(jc.get("role")) if jc.get("role") else None
        if not role:
            await interaction.response.send_message(
                "❌ Devi prima fare il **Setup** del Jail.", ephemeral=True)
            return

        await interaction.response.defer()
        for ch in guild.channels:
            if ch.id == jc.get("channel"):
                continue
            try:
                await ch.set_permissions(role, view_channel=False, reason="Jail: aggiornamento canali")
            except discord.HTTPException:
                pass
        await interaction.followup.send("🔄 Canali aggiornati: il ruolo Jailed è nascosto ovunque.", ephemeral=True)


class JailLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📂 Canale log jail/unjail...",
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
            stato = f"✅ Configurato\n🎭 Ruolo: {role.mention}\n📁 Canale: {channel.mention}"
        else:
            stato = "❌ Non configurato — premi **Setup** per crearlo."
        log_txt = log.mention if log else "❌ non impostato"

        embed = discord.Embed(
            title="🔒 Jail",
            description=(
                "Sistema di isolamento: chi è in jail vede **solo** il canale jail.\n\n"
                "• **Setup** — crea il ruolo *Jailed* e il canale *jail*, e nasconde tutti i canali\n"
                "• **Aggiorna canali** — ri-applica le permissioni (i canali nuovi sono comunque automatici)\n\n"
                "Comandi: `/jail`, `/unjail`, `/jailed`"
            ),
            color=BLU,
        )
        embed.add_field(name="Stato", value=stato, inline=False)
        embed.add_field(name="📂 Canale log", value=log_txt, inline=False)
        return embed


class DMLockView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(DMLockButton(guild.dms_paused()))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        stato = "🟢 In pausa" if self.guild.dms_paused() else "🔴 Attivi"
        embed = discord.Embed(
            title="🔒 DM Lock",
            description="Mette in pausa i DM tra i membri del server (durata max 24h, limite di Discord).",
            color=BLU)
        embed.add_field(name="Stato", value=stato, inline=False)
        return embed


class JoinLockView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(JoinLockButton(guild.invites_paused()))
        self.add_item(BackButton("mod"))

    def build_embed(self) -> discord.Embed:
        stato = "🟢 In pausa" if self.guild.invites_paused() else "🔴 Attivi"
        embed = discord.Embed(
            title="🚪 Join Lock",
            description="Mette in pausa gli inviti: nessuno può entrare (durata max 24h, limite di Discord).",
            color=BLU)
        embed.add_field(name="Stato", value=stato, inline=False)
        return embed


class ModSectionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🚨 Antispam", value="antispam", description="Protezione spam/raid/scam"),
            discord.SelectOption(label="🔒 Jail", value="jail", description="Sistema di isolamento"),
            discord.SelectOption(label="⚠️ Regole Warn", value="warn", description="Azioni automatiche sui warn"),
            discord.SelectOption(label="🎭 Autorole", value="autorole", description="Ruoli automatici all'ingresso"),
            discord.SelectOption(label="🔑 Permessi", value="permessi", description="Chi può usare warn/jail/lock"),
            discord.SelectOption(label="🔒 DM Lock", value="dmlock", description="Pausa DM del server"),
            discord.SelectOption(label="🚪 Join Lock", value="joinlock", description="Pausa inviti del server"),
        ]
        super().__init__(placeholder="Scegli cosa configurare...", options=options)

    async def callback(self, interaction: discord.Interaction):
        a, g = self.view.author_id, self.view.guild
        mappa = {
            "antispam": AntispamView, "jail": JailView, "warn": WarnActionsView,
            "autorole": AutoroleView, "permessi": PermissionsView,
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
        antispam = "🟢 Attivo" if config.get("antispam", {}).get("enabled") else "🔴 Disattivo"
        dm = "🟢 In pausa" if self.guild.dms_paused() else "🔴 Attivi"
        join = "🟢 In pausa" if self.guild.invites_paused() else "🔴 Attivi"
        n_regole = len(config.get("warn_actions", []))

        embed = discord.Embed(
            title="🛡️ Moderazione",
            description="Seleziona cosa configurare dal menu qui sotto.",
            color=BLU,
        )
        embed.add_field(name="Stato rapido", value=(
            f"🚨 Antispam: {antispam}\n"
            f"🔒 DM Lock: {dm}\n"
            f"🚪 Join Lock: {join}\n"
            f"⚠️ Regole Warn: {n_regole} attive"
        ), inline=False)
        return embed


# ── ANTISPAM ──────────────────────────────────────────────────────────────────
def _antispam_cfg(guild_id):
    config = db.get_log_config(guild_id)
    config.setdefault("antispam", {})
    return config


class ToggleAntispamButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label="Antispam", emoji="🚨",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["enabled"] = not config["antispam"].get("enabled", False)
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ToggleAntiscamButton(discord.ui.Button):
    def __init__(self, attivo: bool):
        super().__init__(label="Anti-scam (link)", emoji="🎣",
                         style=discord.ButtonStyle.success if attivo else discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["antiscam"] = not config["antispam"].get("antiscam", False)
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AntispamLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📂 Canale dei log antispam...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"]["log_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = AntispamView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class OpenWhitelistButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Whitelist", emoji="✅", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class OpenCategoriesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Categorie & Sanzioni", emoji="⚙️", style=discord.ButtonStyle.secondary, row=2)

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
        log = f"<#{asc['log_channel']}>" if asc.get("log_channel") else "❌ non impostato"
        embed = discord.Embed(
            title="🚨 Antispam",
            description="Protezione automatica contro spam, raid e truffe.",
            color=BLU,
        )
        embed.add_field(name="Stato", value="🟢 Attivo" if asc.get("enabled") else "🔴 Disattivo", inline=True)
        embed.add_field(name="Anti-scam", value="🟢 Attivo" if asc.get("antiscam") else "🔴 Disattivo", inline=True)
        embed.add_field(name="📂 Canale log", value=log, inline=False)
        embed.add_field(
            name="✅ Whitelist",
            value=(f"{len(wl.get('channels', []))} canali, "
                   f"{len(wl.get('roles', []))} ruoli, "
                   f"{len(wl.get('users', []))} utenti"),
            inline=False,
        )
        return embed


# ── WHITELIST ─────────────────────────────────────────────────────────────────
def _dv(ids, tipo):
    return [discord.SelectDefaultValue(id=i, type=tipo) for i in ids]


class WLChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Canali esenti...", min_values=0, max_values=25, row=0,
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
        super().__init__(placeholder="Ruoli esenti...", min_values=0, max_values=25, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = _antispam_cfg(interaction.guild_id)
        config["antispam"].setdefault("whitelist", {})["roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = WhitelistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class WLUserSelect(discord.ui.UserSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Utenti esenti...", min_values=0, max_values=25, row=2,
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
            title="✅ Whitelist Antispam",
            description="Canali, ruoli e utenti esentati dall'antispam.\n"
                        "Seleziona tutti quelli desiderati in ogni menu (la selezione sostituisce la lista).",
            color=BLU,
        )
        return embed


# ── CATEGORIE & SANZIONI ──────────────────────────────────────────────────────
class SpamCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=lab, value=k) for k, lab in SPAM_CATEGORIES.items()]
        super().__init__(placeholder="Scegli una categoria da configurare...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = SpamCategoryConfigView(self.view.author_id, self.view.guild, self.values[0])
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class SpamCategoriesView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(SpamCategorySelect())
        self.add_item(BackButton("antispam"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        righe = []
        for k, lab in SPAM_CATEGORIES.items():
            c = categoria_cfg(config, k)
            stato = "🟢" if c["enabled"] else "🔴"
            sanz = SANCTIONS.get(c["sanction"], c["sanction"])
            if c["sanction"] == "timeout" and c["seconds"]:
                sanz += f" {c['seconds'] // 60}min"
            righe.append(f"{stato} **{lab}** → {sanz}")
        embed = discord.Embed(title="⚙️ Categorie & Sanzioni", color=BLU,
                              description="\n".join(righe))
        embed.set_footer(text="Scegli una categoria per modificarla")
        return embed


class ToggleCategoryButton(discord.ui.Button):
    def __init__(self, category, attivo):
        super().__init__(label="Attiva/Disattiva", emoji="🔘",
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
    def __init__(self, category, corrente):
        self.category = category
        options = [discord.SelectOption(label=lab, value=k, default=(k == corrente))
                   for k, lab in SANCTIONS.items()]
        super().__init__(placeholder="Sanzione...", options=options, row=0)

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
        super().__init__(placeholder="Durata timeout...", options=options, row=1)

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
        self.add_item(SanctionSelect(category, c["sanction"]))
        self.add_item(SanctionDurationSelect(category, c.get("seconds", 600)))
        self.add_item(ToggleCategoryButton(category, c["enabled"]))
        self.add_item(BackButton("categories"))

    def build_embed(self) -> discord.Embed:
        c = categoria_cfg(db.get_log_config(self.guild.id), self.category)
        sanz = SANCTIONS.get(c["sanction"], c["sanction"])
        embed = discord.Embed(title=f"⚙️ {SPAM_CATEGORIES[self.category]}", color=BLU)
        embed.add_field(name="Stato", value="🟢 Attiva" if c["enabled"] else "🔴 Disattiva", inline=True)
        embed.add_field(name="Sanzione", value=sanz, inline=True)
        if c["sanction"] == "timeout":
            embed.add_field(name="Durata", value=f"{c.get('seconds', 600) // 60} min", inline=True)
        embed.set_footer(text="La durata vale solo per la sanzione Timeout")
        return embed


# ── CONFESSION ────────────────────────────────────────────────────────────────
class ConfessionChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📢 Canale delle confessioni...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        cfg = db.get_config(interaction.guild_id)
        cur_log = cfg["log_channel"] if cfg else None
        db.set_confession_channels(interaction.guild_id, self.values[0].id, cur_log)
        v = ConfessionSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class ConfessionLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="🕵️ Canale log staff (anti-abuso)...",
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
        attiva = "🟢 Attiva" if db.get_log_config(self.guild.id).get("features", {}).get("confession", True) else "🔴 Disattivata"
        ch = self.guild.get_channel(cfg["confession_channel"]) if cfg and cfg["confession_channel"] else None
        log = self.guild.get_channel(cfg["log_channel"]) if cfg and cfg["log_channel"] else None
        embed = discord.Embed(
            title="🤫 Confession",
            description="Attiva/disattiva la funzione e imposta i canali delle confessioni anonime.",
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="📢 Canale confessioni", value=ch.mention if ch else "❌ non impostato", inline=False)
        embed.add_field(name="🕵️ Log staff", value=log.mention if log else "❌ non impostato (opzionale)", inline=False)
        return embed


# ── AUTOROLE ──────────────────────────────────────────────────────────────────
class AutoroleSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder="🎭 Ruoli da assegnare all'ingresso...",
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
            title="🎭 Autorole",
            description="Ruoli assegnati automaticamente a chi entra nel server.\n"
                        "Seleziona i ruoli desiderati nel menu (la selezione sostituisce la lista).",
            color=BLU,
        )
        embed.add_field(name="Ruoli attivi", value=" ".join(ruoli) if ruoli else "*nessuno*", inline=False)
        return embed


# ── PERMESSI MOD (per categoria: lock / jail / warn) ──────────────────────────
MOD_PERM_CATS = {
    "lock": ("🔒 Lock canali", "lock / unlock"),
    "jail": ("⛓️ Jail", "jail / unjail / jailed"),
    "warn": ("⚠️ Warn", "warn / warnings / delwarn / clearwarns"),
}


class ModPermSelect(discord.ui.RoleSelect):
    def __init__(self, categoria, label, ids, row):
        super().__init__(placeholder=f"{label} — ruoli autorizzati...",
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
            title="🔑 Permessi comandi moderazione",
            description=(
                "Tra chi **vede** i comandi (ha *Moderare membri*), scegli **quali ruoli** "
                "possono davvero usarli, per categoria.\n"
                "Gli **Amministratori** possono sempre. Se una categoria è vuota, "
                "vale il permesso nativo (chiunque lo veda può usarlo)."
            ),
            color=BLU,
        )
        for cat, (label, comandi) in MOD_PERM_CATS.items():
            ids = perms.get(cat, [])
            ruoli = [self.guild.get_role(r) for r in ids]
            ruoli = [r.mention for r in ruoli if r]
            valore = " ".join(ruoli) if ruoli else "*tutti quelli che lo vedono*"
            embed.add_field(name=f"{label}  ·  `{comandi}`", value=valore, inline=False)
        return embed


# ── PARTNERSHIP ───────────────────────────────────────────────────────────────
class PartnershipChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📢 Canale dove pubblicare le partner...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("partnership", {})["channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = PartnershipSettingsView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PartnershipRolesSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder="🎭 Ruoli che possono fare partnership...",
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
        super().__init__(label="Configura ping", emoji="🔔", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PingConfigModal(self.view))


class PingConfigModal(discord.ui.Modal, title="Configura ping"):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
        ping = db.get_log_config(parent_view.guild.id).get("partnership", {}).get("ping", {})
        self.here = discord.ui.TextInput(
            label="Membri richiesti per pingare @here", required=False, max_length=10,
            default=str(ping.get("here") or ""), placeholder="es. 500")
        self.everyone = discord.ui.TextInput(
            label="Membri richiesti per pingare @everyone", required=False, max_length=10,
            default=str(ping.get("everyone") or ""), placeholder="es. 1000")
        self.custom_role = discord.ui.TextInput(
            label="Ping personalizzato (ID ruolo)", required=False, max_length=25,
            default=str(ping.get("custom_role") or ""), placeholder="ID del ruolo")
        self.custom_members = discord.ui.TextInput(
            label="Ping personalizzato (membri richiesti)", required=False, max_length=10,
            default=str(ping.get("custom_members") or ""), placeholder="numero di membri")
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
        attiva = "🟢 Attiva" if feats.get("partnership", True) else "🔴 Disattivata"
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
            title="🤝 Partnership",
            description=("Sistema di partnership: chi è autorizzato usa `/partnership` per "
                         "pubblicare una partner nel canale dedicato.\n"
                         "Imposta il canale, i ruoli abilitati e i ping in base ai membri."),
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="📢 Canale partner", value=ch.mention if ch else "❌ non impostato", inline=False)
        embed.add_field(name="🎭 Ruoli autorizzati",
                        value=" ".join(roles) if roles else "*nessuno (solo admin)*", inline=False)
        embed.add_field(name="🔔 Ping", value="\n".join(ping_lines) if ping_lines else "*nessuno*", inline=False)
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
        super().__init__(placeholder="📢 Canale degli auto-message...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("automsg", {})["channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = AutoMsgView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgModal(discord.ui.Modal):
    def __init__(self, author_id, guild, msg_id=None):
        super().__init__(title="Auto Message")
        self.author_id = author_id
        self.guild = guild
        self.msg_id = msg_id
        ex = (_automsg_get(db.get_log_config(guild.id), msg_id) or {}) if msg_id is not None else {}
        self.titolo = discord.ui.TextInput(label="Titolo (per ricordartelo)", max_length=100,
                                           default=ex.get("title", ""), placeholder="es. Buongiorno")
        self.orario = discord.ui.TextInput(label="Orario (HH:MM, ora IT)", max_length=5,
                                           default=ex.get("time", "08:00"))
        self.messaggio = discord.ui.TextInput(label="Messaggio", style=discord.TextStyle.paragraph,
                                              max_length=1500, default=ex.get("message", ""),
                                              placeholder="☀️ Buongiorno {server}!")
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
        super().__init__(label="➕ Aggiungi messaggio", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AutoMsgModal(self.view.author_id, self.view.guild))


class AutoMsgManageSelect(discord.ui.Select):
    def __init__(self, messages):
        options = [discord.SelectOption(label=f"{m.get('title', '?')} ({m.get('time', '?')})"[:100],
                                        value=str(m.get("id"))) for m in messages[:25]]
        super().__init__(placeholder="✏️ Modifica / elimina un messaggio...", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = AutoMsgEditView(self.view.author_id, self.view.guild, int(self.values[0]))
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgEditButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✏️ Modifica", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AutoMsgModal(self.view.author_id, self.view.guild, self.view.msg_id))


class AutoMsgDeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🗑️ Elimina", style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        msgs = config.setdefault("automsg", {}).setdefault("messages", [])
        config["automsg"]["messages"] = [m for m in msgs if m.get("id") != self.view.msg_id]
        db.save_log_config(interaction.guild_id, config)
        v = AutoMsgView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class AutoMsgBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Indietro", emoji="⬅️", style=discord.ButtonStyle.secondary, row=0)

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
        embed.add_field(name="🕐 Orario", value=m.get("time", "?"), inline=False)
        embed.add_field(name="💬 Messaggio", value=(m.get("message") or "*vuoto*")[:1000], inline=False)
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
        attiva = "🟢 Attiva" if feats.get("automsg", True) else "🔴 Disattivata"
        ch = self.guild.get_channel(am.get("channel")) if am.get("channel") else None
        righe = [f"• **{m.get('title')}** — {m.get('time')}" for m in am.get("messages", [])]
        embed = discord.Embed(
            title="📨 Auto Message",
            description=("Messaggi automatici inviati a un orario fisso (**ora italiana**).\n"
                         "Aggiungine quanti vuoi: ognuno ha **titolo**, **orario** e **testo**."),
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="📢 Canale", value=ch.mention if ch else "❌ non impostato", inline=False)
        embed.add_field(name="Messaggi", value="\n".join(righe)[:1000] if righe else "*nessuno*", inline=False)
        embed.add_field(name="Variabili", value="`{server}` · `{membercount}`", inline=False)
        return embed


# ── REACTION AUTOMATICHE ──────────────────────────────────────────────────────
def _parse_emojis(testo, guild=None):
    """Estrae fino a 5 emoji. Accetta unicode, <:nome:id> e anche solo il NOME
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
                if len(out) >= 5:
                    break
                continue
        out.append(tok)
        if len(out) >= 5:
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
class AutoReactWordModal(discord.ui.Modal, title="Reaction su parola"):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.parola = discord.ui.TextInput(label="Parola / frase", max_length=100)
        self.add_item(self.parola)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.parola.value.strip():
            return await interaction.response.send_message("❌ Scrivi una parola.", ephemeral=True)
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
        super().__init__(placeholder="Scegli l'utente (reagisce quando viene pingato)...",
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
        super().__init__(label="Indietro", emoji="⬅️", style=discord.ButtonStyle.secondary, row=row)

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
        super().__init__(label="➕ Parola", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AutoReactWordModal(self.view.author_id, self.view.guild))


class AutoReactAddUserButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="➕ @Utente", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        v = AutoReactAddUserView(self.view.author_id, self.view.guild)
        embed = discord.Embed(title="➕ Reaction su utente",
                              description="Scegli l'utente: il bot reagirà quando viene **pingato**.", color=BLU)
        await interaction.response.edit_message(embed=embed, view=v)


class AutoReactBlacklistSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Canali dove NON reagire...",
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
    def __init__(self, guild, rules):
        options = []
        for r in rules[:25]:
            emo = " ".join(r.get("emojis", []))[:20] or "no emoji"
            if r.get("type") == "mention":
                member = guild.get_member(int(r["trigger"])) if str(r.get("trigger", "")).isdigit() else None
                lab = f"@{member.display_name if member else r['trigger']} → {emo}"
            else:
                modo = "esatta" if r.get("mode") == "exact" else "contiene"
                lab = f"'{r.get('trigger')}' ({modo}) → {emo}"
            options.append(discord.SelectOption(label=lab[:100], value=str(r.get("id"))))
        super().__init__(placeholder="✏️ Modifica una reaction...", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = RuleEditView(self.view.author_id, self.view.guild, int(self.values[0]))
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


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
              if tot > 1 else "😀 Scegli emoji dal server (max 5)...")
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


class RuleEmojiModal(discord.ui.Modal, title="Emoji (scrivi o cerca)"):
    def __init__(self, author_id, guild, rule_id):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.rule_id = rule_id
        r = _autoreact_get(db.get_log_config(guild.id), rule_id) or {}
        self.emoji = discord.ui.TextInput(
            label="Emoji o nomi (max 5, separati da spazio)", required=False,
            default=" ".join(r.get("emojis", [])),
            placeholder="😀  :nomeemoji:  fuoco  <:custom:123>", max_length=200)
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
        super().__init__(label="🔤 Emoji a mano", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RuleEmojiModal(self.view.author_id, self.view.guild, self.view.rule_id))


class RuleWordEditModal(discord.ui.Modal, title="Cambia parola"):
    def __init__(self, author_id, guild, rule_id):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.rule_id = rule_id
        r = _autoreact_get(db.get_log_config(guild.id), rule_id) or {}
        self.parola = discord.ui.TextInput(label="Parola / frase", default=r.get("trigger", ""), max_length=100)
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
        super().__init__(label="✏️ Cambia parola", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RuleWordEditModal(self.view.author_id, self.view.guild, self.view.rule_id))


class RuleModeButton(discord.ui.Button):
    def __init__(self, rule):
        is_exact = rule.get("mode") == "exact"
        if rule.get("type") == "mention":
            stato = "solo il tag" if is_exact else "ovunque"
        else:
            stato = "solo la parola" if is_exact else "ovunque"
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
        super().__init__(label="🗑️ Elimina", style=discord.ButtonStyle.danger, row=2)

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
        emo = " ".join(r.get("emojis", [])) or "*nessuna — scegline dal menu!*"
        if r.get("type") == "mention":
            quando = f"quando viene pingato <@{r.get('trigger')}>"
        else:
            modo = "solo la parola esatta" if r.get("mode") == "exact" else "se la parola è contenuta"
            quando = f"parola `{r.get('trigger')}` ({modo})"
        embed = discord.Embed(title="✏️ Modifica reaction", color=BLU,
                              description=f"**Quando:** {quando}\n**Emoji:** {emo}")
        embed.set_footer(text="Emoji dal menu (server) oppure 'Emoji a mano' per unicode/altre.")
        return embed


class AutoReactView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        _autoreact_ensure_ids(guild.id)
        config = db.get_log_config(guild.id)
        feats = config.get("features", {})
        ar = config.get("autoreact", {})
        self.add_item(FeatureToggleButton("autoreact", feats.get("autoreact", True)))
        self.add_item(AutoReactAddWordButton())
        self.add_item(AutoReactAddUserButton())
        self.add_item(AutoReactBlacklistSelect(ar.get("blacklist_channels", [])))
        if ar.get("rules"):
            self.add_item(AutoReactManageSelect(guild, ar["rules"]))
        self.add_item(BackButton("features"))

    def build_embed(self) -> discord.Embed:
        config = db.get_log_config(self.guild.id)
        feats = config.get("features", {})
        ar = config.get("autoreact", {})
        attiva = "🟢 Attiva" if feats.get("autoreact", True) else "🔴 Disattivata"
        righe = []
        for r in ar.get("rules", []):
            emo = " ".join(r.get("emojis", [])) or "*no emoji*"
            if r.get("type") == "mention":
                righe.append(f"• <@{r['trigger']}> → {emo}")
            else:
                modo = "solo la parola" if r.get("mode") == "exact" else "se contenuta"
                righe.append(f"• `{r.get('trigger')}` ({modo}) → {emo}")
        embed = discord.Embed(
            title="⭐ Reaction automatiche",
            description=("Il bot reagisce quando un messaggio contiene una **parola** "
                         "(esatta o contenuta) o quando un **utente** viene pingato. Max 5 emoji a regola.\n"
                         "Seleziona una regola dal menu per **modificarla** (emoji, parola, eliminarla)."),
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="Regole", value="\n".join(righe)[:1000] if righe else "*nessuna*", inline=False)
        bl = ar.get("blacklist_channels", [])
        embed.add_field(name="🚫 Canali esclusi", value=f"{len(bl)} canali" if bl else "*nessuno*", inline=False)
        return embed


def _feature_view(key: str, author_id: int, guild: discord.Guild):
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
        super().__init__(label="Disattiva" if enabled else "Attiva",
                         emoji="🟢" if enabled else "🔴",
                         style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger, row=0)
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
        feats = db.get_log_config(self.guild.id).get("features", {})
        stato = "🟢 Attiva" if feats.get(self.key, True) else "🔴 Disattivata"
        embed = discord.Embed(title=f"🔧 {FEATURES[self.key]}", color=BLU)
        embed.add_field(name="Stato", value=stato, inline=False)
        return embed


class FeatureSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=lab, value=k) for k, lab in FEATURES.items()]
        super().__init__(placeholder="Scegli una funzione da configurare...", options=options)

    async def callback(self, interaction: discord.Interaction):
        v = _feature_view(self.values[0], self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class FeaturesView(BaseView):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(author_id, guild)
        self.add_item(FeatureSelect())
        self.add_item(BackButton("home"))

    def build_embed(self) -> discord.Embed:
        feats = db.get_log_config(self.guild.id).get("features", {})
        righe = [f"{'🟢' if feats.get(k, True) else '🔴'} {lab}" for k, lab in FEATURES.items()]
        embed = discord.Embed(
            title="🔧 Funzioni del bot",
            description="Seleziona una funzione dal menu per attivarla/disattivarla e configurarla.",
            color=BLU,
        )
        embed.add_field(name="Stato", value="\n".join(righe), inline=False)
        return embed


# ── PROFILO UTENTE ────────────────────────────────────────────────────────────
def _profile_cfg(guild_id: int):
    config = db.get_log_config(guild_id)
    return config, config.setdefault("profile", {})


class ProfileSectionSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            ("🎭 Categorie ruoli", "rolecats", "Categorie di self-role per il +profile"),
            ("🛡️ Bypass privacy", "bypass", "Ruoli che vedono avatar/banner/quote di tutti"),
            ("🔊 Vocali private", "voices", "Collega un canale vocale a un utente"),
            ("⭐ Custom reactions", "react", "Ruoli abilitati e numero max di emoji"),
            ("🏅 Ruolo primario", "primary", "Ruolo speciale mostrato nel profilo"),
        ]
        super().__init__(placeholder="Apri una sotto-sezione...", row=1,
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
        attiva = "🟢 Attiva" if config.get("features", {}).get("profile", True) else "🔴 Disattivata"
        bypass = prof.get("privacy_bypass_roles", [])
        voices = prof.get("private_voices", {})
        allowed = prof.get("custom_react", {}).get("allowed_roles", [])
        primary = prof.get("primary_roles", {})
        embed = discord.Embed(
            title="👤 Profilo utente",
            description="Comando `+profile`. Da qui gestisci i permessi e le assegnazioni.",
            color=BLU,
        )
        embed.add_field(name="Stato", value=attiva, inline=False)
        embed.add_field(name="🛡️ Bypass privacy", value=f"{len(bypass)} ruoli", inline=True)
        embed.add_field(name="🔊 Vocali private", value=f"{len(voices)} assegnate", inline=True)
        embed.add_field(name="⭐ Custom reactions", value=f"{len(allowed)} ruoli", inline=True)
        embed.add_field(name="🏅 Ruoli primari", value=f"{len(primary)} assegnati", inline=True)
        embed.set_footer(text="Scegli una sotto-sezione dal menu")
        return embed


class BypassRolesSelect(discord.ui.RoleSelect):
    def __init__(self, current):
        super().__init__(placeholder="Ruoli che ignorano la privacy altrui...",
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
            title="🛡️ Bypass privacy",
            description="Questi ruoli possono vedere **avatar/banner/quote** anche di chi ha la privacy attiva.",
            color=BLU,
        )
        embed.add_field(name="Ruoli abilitati", value=testo, inline=False)
        return embed


class PrivateVoiceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="1️⃣ Canale vocale...", row=0,
                         channel_types=[discord.ChannelType.voice], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_channel = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrivateVoiceUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="2️⃣ Utente a cui assegnarla...", row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_user = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrivateVoiceLinkButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Collega", emoji="🔗", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if not v.pending_channel or not v.pending_user:
            await interaction.response.send_message(
                "❌ Scegli prima un canale e un utente.", ephemeral=True)
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
                label=(ch.name if ch else f"canale {cid}")[:80], value=str(cid),
                description=f"Assegnata a un utente ({uid})"))
        super().__init__(placeholder="🗑️ Rimuovi un'assegnazione...", row=3,
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
                nome = ch.mention if ch else f"`canale {cid}`"
                righe.append(f"{nome} → <@{uid}>")
            testo = "\n".join(righe)
        else:
            testo = "*Nessuna vocale assegnata.*"
        embed = discord.Embed(
            title="🔊 Vocali private",
            description="Crea tu il canale, poi scegli **canale + utente** e premi Collega.",
            color=BLU,
        )
        embed.add_field(name="Assegnazioni", value=testo, inline=False)
        if self.pending_channel or self.pending_user:
            c = f"<#{self.pending_channel}>" if self.pending_channel else "?"
            u = f"<@{self.pending_user}>" if self.pending_user else "?"
            embed.add_field(name="✏️ In attesa", value=f"{c} → {u}", inline=False)
        return embed


class CustomReactRolesSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Ruoli abilitati alle custom reactions...",
                         min_values=0, max_values=25, row=0)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        cr = prof.setdefault("custom_react", {})
        cr["allowed_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = CustomReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CustomReactMaxSelect(discord.ui.Select):
    def __init__(self, current):
        opts = [discord.SelectOption(label=f"{n} emoji", value=str(n), default=(n == current))
                for n in range(1, 6)]
        super().__init__(placeholder="Numero massimo di emoji...", row=1, options=opts)

    async def callback(self, interaction: discord.Interaction):
        config, prof = _profile_cfg(interaction.guild_id)
        prof.setdefault("custom_react", {})["max"] = int(self.values[0])
        db.save_log_config(interaction.guild_id, config)
        v = CustomReactView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class CustomReactView(BaseView):
    def __init__(self, author_id, guild):
        super().__init__(author_id, guild)
        cr = db.get_log_config(guild.id).get("profile", {}).get("custom_react", {})
        self.add_item(CustomReactRolesSelect())
        self.add_item(CustomReactMaxSelect(cr.get("max", 3)))
        self.add_item(BackButton("profile"))

    def build_embed(self) -> discord.Embed:
        cr = db.get_log_config(self.guild.id).get("profile", {}).get("custom_react", {})
        allowed = cr.get("allowed_roles", [])
        testo = " ".join(f"<@&{r}>" for r in allowed) if allowed else "*Nessuno*"
        embed = discord.Embed(
            title="⭐ Custom reactions",
            description="Chi ha uno dei ruoli abilitati sceglie le proprie emoji dal `+profile`; "
                        "il bot reagisce ai suoi messaggi.",
            color=BLU,
        )
        embed.add_field(name="Ruoli abilitati", value=testo, inline=False)
        embed.add_field(name="Max emoji a testa", value=str(cr.get("max", 3)), inline=False)
        return embed


class PrimaryRoleUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="1️⃣ Utente...", row=0, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_user = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrimaryRoleRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="2️⃣ Ruolo primario...", row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_role = self.values[0].id
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class PrimaryRoleAssignButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Assegna", emoji="✅", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if not v.pending_user or not v.pending_role:
            await interaction.response.send_message(
                "❌ Scegli prima un utente e un ruolo.", ephemeral=True)
            return
        config, prof = _profile_cfg(interaction.guild_id)
        prof.setdefault("primary_roles", {})[str(v.pending_user)] = v.pending_role
        db.save_log_config(interaction.guild_id, config)
        v.pending_user = v.pending_role = None
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class PrimaryRoleRemoveSelect(discord.ui.Select):
    def __init__(self, primary):
        options = [discord.SelectOption(label=f"utente {uid}", value=str(uid))
                   for uid in list(primary.keys())[:25]]
        super().__init__(placeholder="🗑️ Rimuovi un'assegnazione...", row=3,
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
            testo = "*Nessuna assegnazione.*"
        embed = discord.Embed(
            title="🏅 Ruolo primario",
            description="Il ruolo speciale mostrato in cima al `+profile` dell'utente.",
            color=BLU,
        )
        embed.add_field(name="Assegnazioni", value=testo, inline=False)
        if self.pending_user or self.pending_role:
            u = f"<@{self.pending_user}>" if self.pending_user else "?"
            r = f"<@&{self.pending_role}>" if self.pending_role else "?"
            embed.add_field(name="✏️ In attesa", value=f"{u} → {r}", inline=False)
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
        super().__init__(title="Categoria ruoli")
        self.author_id = author_id
        self.guild = guild
        self.cat_id = cat_id
        cat = {}
        if cat_id:
            cat = db.get_log_config(guild.id).get("profile", {}).get("role_categories", {}).get(cat_id, {})
        self.nome = discord.ui.TextInput(label="Nome", max_length=80,
                                         default=cat.get("name", ""), placeholder="Provenienza")
        self.emoji = discord.ui.TextInput(label="Emoji (opzionale)", required=False,
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
        super().__init__(label="Nuova categoria", emoji="➕",
                         style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CategoryModal(self.view.author_id, self.view.guild))


class CategoryEditSelect(discord.ui.Select):
    def __init__(self, cats):
        options = [discord.SelectOption(label=c.get("name", "Categoria")[:100], value=cid,
                                        emoji=_dash_emoji(c.get("emoji")),
                                        description=f"{len(c.get('roles', []))} ruoli")
                   for cid, c in list(cats.items())[:25]]
        super().__init__(placeholder="Modifica una categoria...", options=options, row=1)

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
            righe = [f"{c.get('emoji', '')} **{c.get('name', '—')}** — "
                     f"{len(c.get('roles', []))} ruoli "
                     f"({'singola' if c.get('single') else 'multipla'})"
                     for c in cats.values()]
            testo = "\n".join(righe)
        else:
            testo = "*Nessuna categoria. Creane una con ➕.*"
        embed = discord.Embed(
            title="🎭 Categorie ruoli",
            description="Categorie di self-role che gli utenti scelgono dal `+profile` → Ruoli.",
            color=BLU,
        )
        embed.add_field(name="Categorie", value=testo, inline=False)
        return embed


class CategoryRolesSelect(discord.ui.RoleSelect):
    def __init__(self, cat_id):
        super().__init__(placeholder="Ruoli di questa categoria...",
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
        super().__init__(label="Scelta: singola" if single else "Scelta: multipla",
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
        super().__init__(label="Rinomina", emoji="✏️",
                         style=discord.ButtonStyle.secondary, row=1)
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CategoryModal(self.view.author_id, self.view.guild, self.cat_id))


class DeleteCategoryButton(discord.ui.Button):
    def __init__(self, cat_id):
        super().__init__(label="Elimina", emoji="🗑️",
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
            title=f"{cat.get('emoji', '')} {cat.get('name', 'Categoria')}".strip(),
            description="Scegli i ruoli, il tipo di scelta e (se vuoi) rinomina o elimina.",
            color=BLU,
        )
        embed.add_field(name="Tipo",
                        value="Scelta singola (un solo ruolo)" if cat.get("single")
                        else "Scelta multipla (più ruoli)", inline=False)
        embed.add_field(name="Ruoli", value=testo, inline=False)
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


class XpCooldownModal(discord.ui.Modal, title="XP & Cooldown"):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        c = ls.cfg(db.get_log_config(guild.id))
        self.xp_msg = discord.ui.TextInput(label="XP per messaggio", default=str(c["xp_message"]), max_length=6)
        self.voice_xp = discord.ui.TextInput(label="XP per intervallo in vocale", default=str(c["voice_xp"]), max_length=6)
        self.cd_text = discord.ui.TextInput(label="Cooldown chat (es. 60s, 1m)",
                                            default=ls.fmt_duration(c["cooldown_text"]), max_length=8)
        self.cd_voice = discord.ui.TextInput(label="Cooldown vocale (es. 1m, 5m)",
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
        super().__init__(label="⚙️ XP & Cooldown", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(XpCooldownModal(self.view.author_id, self.view.guild))


class LevelSectionSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            ("📈 Curva XP", "curva", "Base, incremento e override per livello"),
            ("🎉 Level-up", "levelup", "Canale e messaggio di salita di livello"),
            ("🏅 Ruoli premio", "rewards", "Assegna ruoli a certi livelli"),
            ("✨ Multiplier", "multiplier", "Ruoli che danno XP extra"),
            ("🚫 Blacklist", "blacklist", "Ruoli/utenti esclusi dagli XP"),
        ]
        super().__init__(placeholder="Apri una sotto-sezione...", row=0,
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
            title="📊 Livelli",
            description=("Sistema di XP e livelli. Usa il menu in alto per le sotto-sezioni,\n"
                         "i pulsanti per attivare/disattivare e impostare XP/cooldown.\n"
                         "**Coleave**: azzera gli XP quando un utente esce dal server.\n"
                         "**Reward replace** 🟢 = sostituisce i ruoli premio · 🔴 = li accumula."),
            color=BLU,
        )
        embed.add_field(name="Stato",
                        value=f"{sn(c['enabled'])} Sistema · {sn(c['text_enabled'])} Chat · {sn(c['voice_enabled'])} Vocale",
                        inline=False)
        embed.add_field(name="XP per messaggio", value=f"{c['xp_message']}", inline=True)
        embed.add_field(name="XP per vocale", value=f"{c['voice_xp']}", inline=True)
        embed.add_field(name="Cooldown",
                        value=f"chat {ls.fmt_duration(c['cooldown_text'])} · voce {ls.fmt_duration(c['cooldown_voice'])}",
                        inline=True)
        embed.add_field(name="Coleave", value=sn(c["coleave"]), inline=True)
        embed.add_field(name="Reward replace", value=sn(c["reward_replace"]), inline=True)
        return embed


# — Curva XP (manuale) —
class CurveAddModal(discord.ui.Modal, title="Aggiungi livello"):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.livello = discord.ui.TextInput(label="Livello", placeholder="es. 1", max_length=4)
        self.xp = discord.ui.TextInput(label="XP per salire al livello successivo",
                                       placeholder="es. 1000", max_length=9)
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
        super().__init__(label="➕ Aggiungi / modifica livello", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CurveAddModal(self.view.author_id, self.view.guild))


class CurveBulkModal(discord.ui.Modal, title="Import curva in blocco"):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.testo = discord.ui.TextInput(
            label="XP per livello, in ordine dal livello 0",
            style=discord.TextStyle.paragraph, max_length=4000,
            placeholder="46, 64, 84, 106, 130, ...  (un numero per livello)")
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
        super().__init__(label="📋 Import in blocco", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CurveBulkModal(self.view.author_id, self.view.guild))


class CurveClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🧹 Svuota curva", style=discord.ButtonStyle.danger, row=2)

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
            options.append(discord.SelectOption(label=f"Livello {lvl} → {xp} XP"[:100], value=str(lvl)))
        super().__init__(placeholder="🗑️ Rimuovi un livello...", options=options, row=1)

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
            testo = "*Nessun livello impostato (default: 100 XP a livello).*"
        elif len(items) <= 12:
            testo = "\n".join(f"**Lv {lvl}** → `{xp}` XP per salire" for lvl, xp in items)
        else:
            head = "\n".join(f"**Lv {lvl}** → `{xp}`" for lvl, xp in items[:8])
            testo = f"{head}\n… e altri **{len(items) - 8}** livelli impostati"
        embed = discord.Embed(
            title="📈 Curva XP (manuale)",
            description=("Imposti tu, livello per livello, quanti XP servono per salire al successivo.\n"
                         "**Import in blocco**: incolli tutti i valori in un colpo (dal livello 0).\n"
                         "I livelli senza valore usano quello del livello impostato più vicino sotto."),
            color=BLU,
        )
        embed.add_field(name=f"Livelli impostati ({len(items)})", value=testo, inline=False)
        return embed


# — Level-up (canale + messaggio) —
class LevelUpChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📢 Canale dei messaggi di level-up...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["levelup_channel"] = self.values[0].id
        db.save_log_config(interaction.guild_id, config)
        v = LevelUpView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelUpResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Usa il canale del messaggio", emoji="♻️", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["levelup_channel"] = None
        db.save_log_config(interaction.guild_id, config)
        v = LevelUpView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class LevelUpMessageModal(discord.ui.Modal, title="Embed level-up"):
    def __init__(self, author_id, guild):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        c = ls.cfg(db.get_log_config(guild.id))
        self.titolo = discord.ui.TextInput(
            label="Titolo", max_length=256, required=False,
            default=c["levelup_title"], placeholder="{user_name} leveled up!")
        self.msg = discord.ui.TextInput(
            label="Testo", style=discord.TextStyle.paragraph, max_length=1500, required=False,
            default=c["levelup_message"], placeholder="CONGRATS\nSei al livello {level}!")
        self.colore = discord.ui.TextInput(
            label="Colore embed (hex, vuoto = automatico)", max_length=7, required=False,
            default=c["levelup_color"], placeholder="es. F1C40F")
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
        super().__init__(label="✏️ Titolo & Testo", style=discord.ButtonStyle.secondary, row=1)

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
        dove = ch.mention if ch else "Nel canale dove l'utente ha scritto"
        embed = discord.Embed(
            title="🎉 Embed di level-up",
            description=("Embed inviato quando un utente sale di livello (mostra l'avatar dell'utente).\n"
                         "**Variabili:** `{user}` `{user_name}` `{level}` `{server}`"),
            color=BLU,
        )
        embed.add_field(name="📍 Canale", value=dove, inline=False)
        embed.add_field(name="🔤 Titolo", value=f"```{(c['levelup_title'] or '—')[:250]}```", inline=False)
        embed.add_field(name="💬 Testo", value=f"```{(c['levelup_message'] or '—')[:500]}```", inline=False)
        embed.add_field(name="🎨 Colore", value=f"`#{c['levelup_color']}`" if c['levelup_color'] else "Automatico (colore ruolo)", inline=False)
        return embed


# — Ruoli premio —
class RewardLevelModal(discord.ui.Modal, title="Ruolo premio"):
    def __init__(self, author_id, guild, role):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.role = role
        self.livello = discord.ui.TextInput(label=f"Livello per {role.name}", placeholder="es. 10", max_length=4)
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
        super().__init__(placeholder="🏅 Scegli un ruolo da assegnare a un livello...",
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RewardLevelModal(self.view.author_id, self.view.guild, self.values[0]))


class RewardRemoveSelect(discord.ui.Select):
    def __init__(self, guild, rewards):
        options = []
        for lvl, rid in sorted(rewards.items(), key=lambda x: int(x[0])):
            role = guild.get_role(rid)
            nome = role.name if role else f"ruolo {rid}"
            options.append(discord.SelectOption(label=f"Livello {lvl} → {nome}"[:100], value=str(lvl)))
        super().__init__(placeholder="🗑️ Rimuovi un premio...", options=options, row=1)

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
            testo = "*nessun premio impostato*"
        embed = discord.Embed(
            title="🏅 Ruoli premio",
            description=("Assegna un ruolo al raggiungimento di un livello.\n"
                         f"**Reward replace:** {'🟢 sostituisce' if c['reward_replace'] else '🔴 accumula'} "
                         "(modificabile dalla pagina Livelli)."),
            color=BLU,
        )
        embed.add_field(name="Premi", value=testo, inline=False)
        return embed


# — Multiplier —
class MultiplierValueModal(discord.ui.Modal, title="Multiplier ruolo"):
    def __init__(self, author_id, guild, role):
        super().__init__()
        self.author_id = author_id
        self.guild = guild
        self.role = role
        self.valore = discord.ui.TextInput(label=f"Moltiplicatore per {role.name}", placeholder="es. 2 o 1.5",
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
        super().__init__(placeholder="✨ Scegli un ruolo a cui dare un multiplier...",
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            MultiplierValueModal(self.view.author_id, self.view.guild, self.values[0]))


class MultiplierRemoveSelect(discord.ui.Select):
    def __init__(self, guild, mult):
        options = []
        for rid, val in mult.items():
            role = guild.get_role(int(rid))
            nome = role.name if role else f"ruolo {rid}"
            options.append(discord.SelectOption(label=f"{nome} ×{val}"[:100], value=str(rid)))
        super().__init__(placeholder="🗑️ Rimuovi un multiplier...", options=options, row=1)

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
            testo = "*nessun multiplier*"
        embed = discord.Embed(
            title="✨ Multiplier",
            description="Ruoli che danno XP extra. Se un membro ha più ruoli, vale il **moltiplicatore più alto**.",
            color=BLU,
        )
        embed.add_field(name="Multiplier attivi", value=testo, inline=False)
        return embed


# — Blacklist XP —
class XpBlacklistRolesSelect(discord.ui.RoleSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Ruoli esclusi dagli XP...", min_values=0, max_values=25, row=0,
                         default_values=_dv(ids, discord.SelectDefaultValueType.role))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["blacklist_roles"] = [r.id for r in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LevelBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpBlacklistUsersSelect(discord.ui.UserSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Utenti esclusi dagli XP...", min_values=0, max_values=25, row=1,
                         default_values=_dv(ids, discord.SelectDefaultValueType.user))

    async def callback(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        config.setdefault("levels", {})["blacklist_users"] = [u.id for u in self.values]
        db.save_log_config(interaction.guild_id, config)
        v = LevelBlacklistView(self.view.author_id, self.view.guild)
        await interaction.response.edit_message(embed=v.build_embed(), view=v)


class XpBlacklistChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, ids):
        super().__init__(placeholder="Canali esclusi dagli XP (testo, vocale, categorie)...",
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
            title="🚫 Blacklist XP",
            description=("Ruoli, utenti e canali che **non** danno XP.\n"
                         "Seleziona quelli desiderati nei menu (la selezione sostituisce la lista).\n"
                         "Per i canali puoi scegliere anche una **categoria** intera."),
            color=BLU,
        )
        embed.add_field(name="Ruoli esclusi",
                        value=f"{len(c.get('blacklist_roles', []))} ruoli" if c.get("blacklist_roles") else "*nessuno*",
                        inline=True)
        embed.add_field(name="Utenti esclusi",
                        value=f"{len(c.get('blacklist_users', []))} utenti" if c.get("blacklist_users") else "*nessuno*",
                        inline=True)
        embed.add_field(name="Canali esclusi",
                        value=f"{len(c.get('blacklist_channels', []))} canali" if c.get("blacklist_channels") else "*nessuno*",
                        inline=True)
        return embed


# ── COG ───────────────────────────────────────────────────────────────────────
class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dashboard", description="Apri il pannello di configurazione del server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def dashboard(self, interaction: discord.Interaction):
        view = DashboardView(interaction.user.id, interaction.guild)
        embed = build_main_embed(interaction.guild, db.get_log_config(interaction.guild_id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Dashboard(bot))
