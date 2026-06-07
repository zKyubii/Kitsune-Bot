import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db
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
            "🛡️ **Moderazione** — regole automatiche dei warn"
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
        ]
        super().__init__(placeholder="Scegli una sezione...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "logs":
            view = LogsMenuView(self.view.author_id, self.view.guild)
        elif self.values[0] == "mod":
            view = ModerationView(self.view.author_id, self.view.guild)
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


def _feature_view(key: str, author_id: int, guild: discord.Guild):
    if key == "quote":
        return QuoteSettingsView(author_id, guild)
    if key == "confession":
        return ConfessionSettingsView(author_id, guild)
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
