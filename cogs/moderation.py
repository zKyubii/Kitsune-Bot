import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import re

import database as db


def parse_duration(duration_str: str) -> datetime.timedelta | None:
    match = re.fullmatch(r'(\d+)([smhd])', duration_str.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    if unit == 's':
        return datetime.timedelta(seconds=value)
    elif unit == 'm':
        return datetime.timedelta(minutes=value)
    elif unit == 'h':
        return datetime.timedelta(hours=value)
    elif unit == 'd':
        return datetime.timedelta(days=value)


def format_seconds(s: int) -> str:
    if s >= 3600:
        return f"{s // 3600}h"
    elif s >= 60:
        return f"{s // 60} min"
    return f"{s}s"


# Palette colori per le barre laterali — muted e professionali
COLORI = {
    "ban": 0xE74C3C,       # rosso
    "softban": 0x9B59B6,   # viola
    "hackban": 0xC0392B,   # rosso scuro
    "unban": 0x2ECC71,     # verde
    "kick": 0xE67E22,      # arancione
    "timeout": 0xF1C40F,   # giallo
    "untimeout": 0x2ECC71, # verde
    "warn": 0xF1C40F,      # giallo
}

# Badge Discord (nome del flag -> etichetta con emoji)
BADGES = {
    "staff": "🛡️ Discord Staff",
    "partner": "🤝 Partner",
    "hypesquad": "🏠 HypeSquad Events",
    "bug_hunter": "🐛 Bug Hunter",
    "bug_hunter_level_2": "🐛 Bug Hunter Gold",
    "hypesquad_bravery": "🦁 Bravery",
    "hypesquad_brilliance": "💎 Brilliance",
    "hypesquad_balance": "⚖️ Balance",
    "early_supporter": "🌸 Early Supporter",
    "verified_bot_developer": "👨‍💻 Verified Bot Dev",
    "active_developer": "⚙️ Active Developer",
    "discord_certified_moderator": "🛡️ Moderator Program",
}

# Permessi considerati "pericolosi" (per il conteggio ruoli in serverinfo)
PERMESSI_PERICOLOSI = (
    "administrator", "ban_members", "kick_members", "manage_guild",
    "manage_roles", "manage_channels", "manage_messages", "manage_webhooks",
    "mention_everyone", "moderate_members",
)


class ModRoleMissing(app_commands.CheckFailure):
    """Sollevata quando l'utente vede il comando ma non è autorizzato a usarlo."""
    pass


def mod_check(categoria: str):
    """
    Visibilità gestita da default_permissions (permesso nativo).
    Esecuzione: Admin sempre; se il menu Permessi ha ruoli per la categoria,
    solo quei ruoli; se è vuoto, vale il permesso nativo (Moderare membri).
    """
    async def predicate(interaction: discord.Interaction):
        perms = interaction.user.guild_permissions
        if perms.administrator:
            return True
        roles_ok = db.get_log_config(interaction.guild_id).get("mod_perms", {}).get(categoria, [])
        if roles_ok:
            if any(r.id in roles_ok for r in interaction.user.roles):
                return True
        elif perms.moderate_members:
            return True
        raise ModRoleMissing()
    return app_commands.check(predicate)


def build_mod_embed(
    azione: str,
    label: str,
    target,
    moderatore: discord.Member,
    colore: int,
    motivo: str = None,
    durata: str = None,
    extra: dict = None,
    proof: discord.Attachment = None,
) -> discord.Embed:
    """Crea un embed di moderazione in stile pulito e coerente."""
    desc = ""
    if motivo:
        desc += f"📋 **Reason:** {motivo}\n"
    desc += f"👤 **Moderator:** {moderatore.mention}\n"
    if durata:
        desc += f"🕐 **Duration:** {durata}\n"
    if extra:
        for nome, valore in extra.items():
            desc += f"{nome} {valore}\n"
    desc += f"\n**{label}:**\n✅ {target.name} [ `{target.id}` ]"

    embed = discord.Embed(
        title=f"{azione} Result:",
        description=desc,
        color=colore,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"ID: {target.id}")
    if proof:
        embed.add_field(name="🔗 Proof", value=f"[Allegato]({proof.url})", inline=False)
        if proof.content_type and proof.content_type.startswith("image"):
            embed.set_image(url=proof.url)
    return embed


def gerarchia_ok(interaction: discord.Interaction, membro: discord.Member) -> tuple[bool, str]:
    """Controlla che sia il moderatore sia il bot possano agire sul membro."""
    if membro == interaction.user:
        return False, "❌ Non puoi usare questo comando su te stesso."
    if membro.id == interaction.guild.owner_id:
        return False, "❌ Non puoi moderare il proprietario del server."

    # Il moderatore deve essere più in alto (il proprietario bypassa il controllo)
    if interaction.user.id != interaction.guild.owner_id:
        if membro.top_role >= interaction.user.top_role:
            return False, "❌ Non puoi moderare un utente con ruolo uguale o superiore al tuo."

    # Il bot deve essere più in alto del bersaglio
    if membro.top_role >= interaction.guild.me.top_role:
        return False, "❌ Il mio ruolo è troppo basso: spostalo sopra quello dell'utente da moderare."

    return True, ""


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Registro condiviso col cog Logs: quando un'azione la esegue il bot
        # tramite comando, qui salviamo chi l'ha lanciata, così il mod-log
        # mostra il moderatore reale invece del bot.
        if not hasattr(bot, "recent_mod"):
            bot.recent_mod = {}
        self.check_temp_bans.start()

    def cog_unload(self):
        self.check_temp_bans.cancel()

    # ── BAN TEMPORANEI ────────────────────────────────────────────────────────
    @tasks.loop(minutes=1)
    async def check_temp_bans(self):
        """Sblocca i ban temporanei scaduti.

        La scadenza è nel DB, quindi funziona anche se il bot è stato riavviato
        (o è rimasto offline) mentre il ban era in corso.
        """
        for row in db.get_expired_temp_bans():
            guild = self.bot.get_guild(row["guild_id"])
            if guild is None:
                continue  # bot non più in quel server: riproviamo più avanti
            try:
                user = await self.bot.fetch_user(row["user_id"])
                await guild.unban(user, reason=f"Ban temporaneo scaduto ({row['reason'] or ''})".strip())
            except discord.NotFound:
                pass  # già sbannato a mano: ripuliamo comunque il record
            except discord.HTTPException:
                continue  # errore temporaneo: riproviamo al prossimo giro
            db.remove_temp_ban(row["guild_id"], row["user_id"])

    @check_temp_bans.before_loop
    async def before_check_temp_bans(self):
        await self.bot.wait_until_ready()

    def _remember_mod(self, guild_id: int, label: str, target_id: int, moderatore: discord.abc.User):
        self.bot.recent_mod[(guild_id, label, target_id)] = (
            moderatore.id, datetime.datetime.now(datetime.timezone.utc)
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, ModRoleMissing):
            msg = "⛔ Non hai un ruolo autorizzato per questo comando."
        elif isinstance(error, app_commands.MissingPermissions):
            permessi = ", ".join(error.missing_permissions)
            msg = f"⛔ Non hai il permesso necessario per questo comando: `{permessi}`"
        elif isinstance(error, app_commands.BotMissingPermissions):
            permessi = ", ".join(error.missing_permissions)
            msg = f"⚠️ Mi manca il permesso necessario: `{permessi}`"
        else:
            msg = f"❌ Si è verificato un errore: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── BAN ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Banna un utente dal server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str = "Nessun motivo specificato",
        durata: str = None,
        proof: discord.Attachment = None,
        soft_ban: bool = False,
        purge_days: app_commands.Range[int, 0, 7] = 0,
    ):
        ok, errore = gerarchia_ok(interaction, membro)
        if not ok:
            await interaction.response.send_message(errore, ephemeral=True)
            return

        await interaction.response.defer()

        delta = None
        if durata:
            delta = parse_duration(durata)
            if not delta:
                await interaction.followup.send(
                    "❌ Formato durata non valido. Usa es: `30s`, `10m`, `2h`, `7d`", ephemeral=True
                )
                return

        await membro.ban(reason=motivo, delete_message_days=purge_days)
        self._remember_mod(interaction.guild_id, "ban", membro.id, interaction.user)

        extra = {}
        if purge_days > 0:
            extra["🧹 **Purged:**"] = f"ultimi {purge_days} giorni"

        if soft_ban:
            self._remember_mod(interaction.guild_id, "unban", membro.id, interaction.user)
            await interaction.guild.unban(membro, reason="Soft ban — pulizia messaggi")
            embed = build_mod_embed(
                "Soft Ban", "Soft Banned", membro, interaction.user, COLORI["softban"],
                motivo=motivo, extra=extra, proof=proof,
            )
        else:
            embed = build_mod_embed(
                "Ban", "Banned", membro, interaction.user, COLORI["ban"],
                motivo=motivo, durata=(durata if delta else None), extra=extra, proof=proof,
            )

        await interaction.followup.send(embed=embed)

        if delta and not soft_ban:
            scadenza = datetime.datetime.now(datetime.timezone.utc) + delta
            db.add_temp_ban(interaction.guild_id, membro.id, scadenza, durata)

    # ── HACK BAN ──────────────────────────────────────────────────────────────
    @app_commands.command(name="hackban", description="Banna un utente tramite ID (anche se non è nel server)")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def hackban(
        self,
        interaction: discord.Interaction,
        utente_id: str,
        motivo: str = "Nessun motivo specificato",
        proof: discord.Attachment = None,
    ):
        await interaction.response.defer()
        try:
            user = await self.bot.fetch_user(int(utente_id))
            await interaction.guild.ban(user, reason=motivo)
            self._remember_mod(interaction.guild_id, "ban", user.id, interaction.user)

            embed = build_mod_embed(
                "Hack Ban", "Banned", user, interaction.user, COLORI["hackban"],
                motivo=motivo, proof=proof,
            )
            await interaction.followup.send(embed=embed)
        except ValueError:
            await interaction.followup.send("❌ ID non valido.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Utente non trovato.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)

    # ── UNBAN ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Rimuove il ban a un utente")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        utente_id: str,
        motivo: str = "Nessun motivo specificato",
        proof: discord.Attachment = None,
    ):
        await interaction.response.defer()
        try:
            user = await self.bot.fetch_user(int(utente_id))
            await interaction.guild.unban(user, reason=motivo)
            self._remember_mod(interaction.guild_id, "unban", user.id, interaction.user)
            db.remove_temp_ban(interaction.guild_id, user.id)

            embed = build_mod_embed(
                "Unban", "Unbanned", user, interaction.user, COLORI["unban"],
                motivo=motivo, proof=proof,
            )
            await interaction.followup.send(embed=embed)
        except ValueError:
            await interaction.followup.send("❌ ID non valido.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Utente non trovato o non bannato.", ephemeral=True)

    # ── KICK ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kicka un utente dal server")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str = "Nessun motivo specificato",
        proof: discord.Attachment = None,
    ):
        ok, errore = gerarchia_ok(interaction, membro)
        if not ok:
            await interaction.response.send_message(errore, ephemeral=True)
            return

        await interaction.response.defer()
        self._remember_mod(interaction.guild_id, "kick", membro.id, interaction.user)
        await membro.kick(reason=motivo)

        embed = build_mod_embed(
            "Kick", "Kicked", membro, interaction.user, COLORI["kick"],
            motivo=motivo, proof=proof,
        )
        await interaction.followup.send(embed=embed)

    # ── TIMEOUT ───────────────────────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Mette in timeout un utente")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        durata: str,
        motivo: str = "Nessun motivo specificato",
        proof: discord.Attachment = None,
    ):
        ok, errore = gerarchia_ok(interaction, membro)
        if not ok:
            await interaction.response.send_message(errore, ephemeral=True)
            return

        delta = parse_duration(durata)
        if not delta:
            await interaction.response.send_message(
                "❌ Formato durata non valido. Usa es: `30s`, `10m`, `2h`, `7d`", ephemeral=True
            )
            return

        if delta > datetime.timedelta(days=28):
            await interaction.response.send_message(
                "❌ Il timeout massimo consentito da Discord è **28 giorni** (`28d`).", ephemeral=True
            )
            return

        await interaction.response.defer()
        self._remember_mod(interaction.guild_id, "timeout", membro.id, interaction.user)
        await membro.timeout(delta, reason=motivo)

        embed = build_mod_embed(
            "Timeout", "Timed out", membro, interaction.user, COLORI["timeout"],
            motivo=motivo, durata=durata, proof=proof,
        )
        await interaction.followup.send(embed=embed)

    # ── UNTIMEOUT ─────────────────────────────────────────────────────────────
    @app_commands.command(name="untimeout", description="Rimuove il timeout a un utente")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, membro: discord.Member):
        self._remember_mod(interaction.guild_id, "timeout", membro.id, interaction.user)
        await membro.timeout(None)
        embed = build_mod_embed(
            "Untimeout", "Timeout removed", membro, interaction.user, COLORI["untimeout"],
        )
        await interaction.response.send_message(embed=embed)

    # ── SLOWMODE ──────────────────────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Imposta il slowmode nel canale")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.choices(preset=[
        app_commands.Choice(name="🚫 Disattiva", value=0),
        app_commands.Choice(name="1 minuto", value=60),
        app_commands.Choice(name="5 minuti", value=300),
        app_commands.Choice(name="10 minuti", value=600),
        app_commands.Choice(name="15 minuti", value=900),
        app_commands.Choice(name="30 minuti", value=1800),
        app_commands.Choice(name="1 ora", value=3600),
        app_commands.Choice(name="2 ore", value=7200),
        app_commands.Choice(name="3 ore", value=10800),
        app_commands.Choice(name="6 ore", value=21600),
    ])
    async def slowmode(
        self,
        interaction: discord.Interaction,
        preset: app_commands.Choice[int] = None,
        personalizzato: app_commands.Range[int, 0, 21600] = None,
    ):
        if preset is None and personalizzato is None:
            await interaction.response.send_message(
                "❌ Scegli un preset oppure inserisci un valore personalizzato in secondi.", ephemeral=True
            )
            return

        secondi = personalizzato if personalizzato is not None else preset.value
        await interaction.channel.edit(slowmode_delay=secondi)

        if secondi == 0:
            await interaction.response.send_message("✅ Slowmode disattivato.")
        else:
            await interaction.response.send_message(f"🐢 Slowmode impostato a **{format_seconds(secondi)}**.")

    # ── CLEAR ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="clear", description="Cancella messaggi dal canale con filtri opzionali")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        quantita: app_commands.Range[int, 1, 100],
        utente: discord.Member = None,
        solo_link: bool = False,
        solo_immagini: bool = False,
        solo_bot: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)

        def check(msg: discord.Message) -> bool:
            if utente and msg.author != utente:
                return False
            if solo_bot and not msg.author.bot:
                return False
            if solo_link:
                ha_link = any(w.startswith(("http://", "https://")) for w in msg.content.split())
                if not ha_link:
                    return False
            if solo_immagini:
                ha_immagine = any(
                    a.content_type and a.content_type.startswith("image") for a in msg.attachments
                )
                if not ha_immagine:
                    return False
            return True

        eliminati = await interaction.channel.purge(limit=quantita, check=check)
        await interaction.followup.send(f"🗑️ Eliminati **{len(eliminati)}** messaggi.", ephemeral=True)


    # ── BANLIST ───────────────────────────────────────────────────────────────
    @app_commands.command(name="banlist", description="Mostra la lista degli utenti bannati dal server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def banlist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        bans = [entry async for entry in interaction.guild.bans()]

        if not bans:
            await interaction.followup.send("✅ Non ci sono utenti bannati in questo server.", ephemeral=True)
            return

        view = BanlistView(bans, interaction.user.id)
        await interaction.followup.send(embed=view.crea_embed(), view=view, ephemeral=True)

    # ── WARN ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Avvisa un utente (con motivo e prove opzionali)")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("warn")
    async def warn(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str,
        proof: discord.Attachment = None,
    ):
        if membro == interaction.user:
            await interaction.response.send_message("❌ Non puoi avvisare te stesso.", ephemeral=True)
            return
        if membro.bot:
            await interaction.response.send_message("❌ Non puoi avvisare un bot.", ephemeral=True)
            return

        proof_url = proof.url if proof else None
        warn_id = db.add_warning(interaction.guild_id, membro.id, interaction.user.id, motivo, proof_url)
        totale = len(db.get_warnings(interaction.guild_id, membro.id))

        # Applica eventuale azione automatica configurata dalla dashboard
        auto = await self._applica_auto_warn(interaction.guild, membro, totale)

        embed = discord.Embed(title="⚠️ Warn Result:", color=COLORI.get("warn", 0xF1C40F),
                              timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.description = (
            f"📋 **Reason:** {motivo}\n"
            f"👤 **Moderator:** {interaction.user.mention}\n"
            f"🔢 **Warn totali:** {totale}\n\n"
            f"**Warned:**\n✅ {membro.name} [ `{membro.id}` ]"
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.set_footer(text=f"Warn ID: {warn_id}")
        if proof_url:
            embed.add_field(name="🔗 Proof", value=f"[Allegato]({proof_url})", inline=False)
            if proof.content_type and proof.content_type.startswith("image"):
                embed.set_image(url=proof_url)
        if auto:
            embed.add_field(name="⚙️ Azione automatica", value=auto, inline=False)

        await interaction.response.send_message(embed=embed)

        # Avvisa l'utente in DM (se possibile)
        try:
            dm = discord.Embed(
                title=f"⚠️ Sei stato avvisato in {interaction.guild.name}",
                description=f"📋 **Motivo:** {motivo}",
                color=0xF1C40F,
            )
            await membro.send(embed=dm)
        except discord.HTTPException:
            pass

    # ── WARNINGS ──────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Mostra i warn di un utente")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("warn")
    async def warnings(self, interaction: discord.Interaction, membro: discord.Member):
        warns = db.get_warnings(interaction.guild_id, membro.id)
        if not warns:
            await interaction.response.send_message(
                f"✅ **{membro}** non ha warn.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚠️ Warn di {membro}",
            description=f"Totale: **{len(warns)}**",
            color=0xF1C40F,
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        for w in warns[:25]:
            data = discord.utils.format_dt(datetime.datetime.fromisoformat(w["created_at"]), "R")
            valore = f"📋 {w['reason']}\n👮 <@{w['moderator_id']}> • {data}"
            if w["proof"]:
                valore += f"\n🔗 [Proof]({w['proof']})"
            embed.add_field(name=f"Warn #{w['id']}", value=valore, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── DELWARN ───────────────────────────────────────────────────────────────
    @app_commands.command(name="delwarn", description="Rimuove un warn tramite il suo ID")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("warn")
    async def delwarn(self, interaction: discord.Interaction, warn_id: int):
        if db.remove_warning(interaction.guild_id, warn_id):
            await interaction.response.send_message(f"✅ Warn **#{warn_id}** rimosso.")
        else:
            await interaction.response.send_message(f"❌ Nessun warn con ID #{warn_id}.", ephemeral=True)

    # ── CLEARWARNS ────────────────────────────────────────────────────────────
    @app_commands.command(name="clearwarns", description="Cancella tutti i warn di un utente")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("warn")
    async def clearwarns(self, interaction: discord.Interaction, membro: discord.Member):
        quanti = db.clear_warnings(interaction.guild_id, membro.id)
        if quanti:
            await interaction.response.send_message(
                f"🧹 Rimossi **{quanti}** warn da **{membro}**.")
        else:
            await interaction.response.send_message(
                f"✅ **{membro}** non aveva warn.", ephemeral=True)

    async def _applica_auto_warn(self, guild: discord.Guild, membro: discord.Member, totale: int):
        """Applica l'azione automatica se esiste una regola per questo numero di warn."""
        config = db.get_log_config(guild.id)
        regole = config.get("warn_actions", [])
        regola = next((r for r in regole if r["count"] == totale), None)
        if not regola:
            return None
        azione = regola["action"]
        try:
            if azione == "timeout":
                await membro.timeout(datetime.timedelta(seconds=regola["seconds"]),
                                     reason=f"Auto: raggiunti {totale} warn")
                return f"⏱️ Timeout automatico ({format_seconds(regola['seconds'])})"
            elif azione == "kick":
                await membro.kick(reason=f"Auto: raggiunti {totale} warn")
                return "👢 Kick automatico"
            elif azione == "ban":
                await membro.ban(reason=f"Auto: raggiunti {totale} warn")
                return "🔨 Ban automatico"
        except discord.HTTPException:
            return "⚠️ Azione automatica non riuscita (permessi o ruolo troppo alto)"
        return None

    # ── LOCK ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Blocca un canale (nessuno può più scrivere)")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("lock")
    async def lock(self, interaction: discord.Interaction,
                   canale: discord.TextChannel = None,
                   motivo: str = "Nessun motivo specificato"):
        canale = canale or interaction.channel
        overwrite = canale.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await canale.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=motivo)

        embed = discord.Embed(title="🔒 Canale bloccato", color=COLORI.get("ban", 0xE74C3C),
                              description=f"{canale.mention} è stato bloccato.\n📝 {motivo}")
        await interaction.response.send_message(embed=embed)
        await self._lock_log(interaction, canale, "🔒 Channel Locked", "locked", motivo)

    # ── UNLOCK ────────────────────────────────────────────────────────────────
    @app_commands.command(name="unlock", description="Sblocca un canale precedentemente bloccato")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("lock")
    async def unlock(self, interaction: discord.Interaction,
                     canale: discord.TextChannel = None):
        canale = canale or interaction.channel
        overwrite = canale.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await canale.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(title="🔓 Canale sbloccato", color=0x2ECC71,
                              description=f"{canale.mention} è di nuovo accessibile.")
        await interaction.response.send_message(embed=embed)
        await self._lock_log(interaction, canale, "🔓 Channel Unlocked", "unlocked", None)

    async def _lock_log(self, interaction, canale, titolo, verbo, motivo):
        logs_cog = self.bot.get_cog("Logs")
        if not logs_cog:
            return
        from cogs.logs import _emb
        rest = [f"**Moderator:** {interaction.user.mention}"]
        if motivo:
            rest.append(f"**Reason:** {motivo}")
        colore = 0xE74C3C if verbo == "locked" else 0x2ECC71
        e = _emb(colore, titolo, f"{canale.mention} was **{verbo}**", rest)
        await logs_cog._send(interaction.guild, "modlogs", "lock", e, source_channel_id=canale.id)

    # ── JAIL ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="jail", description="Mette un utente in jail (vede solo il canale jail)")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("jail")
    async def jail(self, interaction: discord.Interaction, membro: discord.Member,
                   motivo: str = "Nessun motivo specificato"):
        config = db.get_log_config(interaction.guild_id)
        jc = config.get("jail", {})
        role = interaction.guild.get_role(jc.get("role")) if jc.get("role") else None
        channel = interaction.guild.get_channel(jc.get("channel")) if jc.get("channel") else None

        if not role or not channel:
            await interaction.response.send_message(
                "❌ Il sistema Jail non è configurato. Vai su `/dashboard` → 🛡️ Moderazione → 🔒 Jail → **Setup**.",
                ephemeral=True)
            return

        ok, errore = gerarchia_ok(interaction, membro)
        if not ok:
            await interaction.response.send_message(errore, ephemeral=True)
            return
        if role in membro.roles:
            await interaction.response.send_message(f"❌ **{membro}** è già in jail.", ephemeral=True)
            return

        await interaction.response.defer()
        da_rimuovere = [r for r in membro.roles
                        if r != interaction.guild.default_role and not r.managed and r < interaction.guild.me.top_role]
        db.set_jailed(interaction.guild_id, membro.id, [r.id for r in da_rimuovere])

        try:
            if da_rimuovere:
                await membro.remove_roles(*da_rimuovere, reason=f"Jail: {motivo}")
            await membro.add_roles(role, reason=f"Jail: {motivo}")
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            return

        embed = discord.Embed(title="🔒 Utente in Jail", color=COLORI.get("ban", 0xE74C3C),
                              description=f"{membro.mention} è stato messo in jail.\n📋 {motivo}")
        await interaction.followup.send(embed=embed)
        try:
            await channel.send(f"🔒 {membro.mention} sei stato messo in **jail**.\n📋 Motivo: {motivo}")
        except discord.HTTPException:
            pass

        log = discord.Embed(title="🔒 Jail", color=COLORI.get("ban", 0xE74C3C),
                            timestamp=datetime.datetime.now(datetime.timezone.utc))
        log.add_field(name="Utente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
        log.add_field(name="Moderatore", value=interaction.user.mention, inline=True)
        log.add_field(name="Motivo", value=motivo, inline=False)
        log.set_thumbnail(url=membro.display_avatar.url)
        await self._jail_log(interaction.guild, log)

    # ── UNJAIL ────────────────────────────────────────────────────────────────
    @app_commands.command(name="unjail", description="Toglie un utente dal jail e ripristina i suoi ruoli")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("jail")
    async def unjail(self, interaction: discord.Interaction, membro: discord.Member):
        config = db.get_log_config(interaction.guild_id)
        role = interaction.guild.get_role(config.get("jail", {}).get("role"))
        if not role or role not in membro.roles:
            await interaction.response.send_message(f"❌ **{membro}** non è in jail.", ephemeral=True)
            return

        await interaction.response.defer()
        salvati = db.get_jailed(interaction.guild_id, membro.id) or []
        ruoli = [interaction.guild.get_role(rid) for rid in salvati]
        ruoli = [r for r in ruoli if r and r < interaction.guild.me.top_role]

        try:
            await membro.remove_roles(role, reason="Unjail")
            if ruoli:
                await membro.add_roles(*ruoli, reason="Unjail: ripristino ruoli")
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            return

        db.remove_jailed(interaction.guild_id, membro.id)
        embed = discord.Embed(title="🔓 Utente liberato", color=0x2ECC71,
                              description=f"{membro.mention} è stato tolto dal jail e i ruoli sono stati ripristinati.")
        await interaction.followup.send(embed=embed)

        log = discord.Embed(title="🔓 Unjail", color=0x2ECC71,
                            timestamp=datetime.datetime.now(datetime.timezone.utc))
        log.add_field(name="Utente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
        log.add_field(name="Moderatore", value=interaction.user.mention, inline=True)
        log.set_thumbnail(url=membro.display_avatar.url)
        await self._jail_log(interaction.guild, log)

    async def _jail_log(self, guild, embed):
        cid = db.get_log_config(guild.id).get("jail", {}).get("log_channel")
        if cid:
            ch = guild.get_channel(cid)
            if ch:
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

    # ── JAILED (lista) ──────────────────────────────────────────────────────────
    @app_commands.command(name="jailed", description="Mostra gli utenti attualmente in jail")
    @app_commands.default_permissions(moderate_members=True)
    @mod_check("jail")
    async def jailed(self, interaction: discord.Interaction):
        config = db.get_log_config(interaction.guild_id)
        role = interaction.guild.get_role(config.get("jail", {}).get("role"))
        if not role:
            await interaction.response.send_message(
                "❌ Il sistema Jail non è configurato.", ephemeral=True)
            return

        membri = role.members
        if not membri:
            await interaction.response.send_message("✅ Nessun utente è attualmente in jail.", ephemeral=True)
            return

        righe = [f"🔒 {m.mention} (`{m.id}`)" for m in membri]
        embed = discord.Embed(
            title=f"🔒 Utenti in Jail ({len(membri)})",
            description="\n".join(righe[:50]),
            color=COLORI.get("ban", 0xE74C3C),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Nasconde automaticamente i nuovi canali al ruolo Jailed
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        config = db.get_log_config(channel.guild.id)
        jc = config.get("jail", {})
        if not jc.get("role") or channel.id == jc.get("channel"):
            return
        role = channel.guild.get_role(jc["role"])
        if role:
            try:
                await channel.set_permissions(role, view_channel=False, reason="Jail: nuovo canale")
            except discord.HTTPException:
                pass

    # ── SERVERINFO ────────────────────────────────────────────────────────────
    @app_commands.command(name="serverinfo", description="Mostra le informazioni del server")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        testuali = len(g.text_channels)
        vocali = len(g.voice_channels)
        managed = sum(1 for r in g.roles if r.managed)
        dangerous = sum(1 for r in g.roles if any(getattr(r.permissions, p) for p in PERMESSI_PERICOLOSI))

        embed = discord.Embed(
            title=f"Server Information [ {g.name} ]",
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)

        embed.description = (
            f"🏷️ **Name:** {g.name}\n"
            f"﹥ **ID:** `{g.id}`\n"
            f"👑 **Owner:** <@{g.owner_id}>\n"
            f"🎂 **Creation:** {discord.utils.format_dt(g.created_at, 'R')}\n\n"
            f"📁 **Channels:** {len(g.channels)}\n"
            f"› 💬 **Text:** {testuali}\n"
            f"› 🔊 **VC:** {vocali}\n\n"
            f"👥 **Members:** {g.member_count}\n\n"
            f"🎭 **Roles:** {len(g.roles)}\n"
            f"› 🤖 **Managed:** {managed}\n"
            f"› ⚠️ **Dangerous:** {dangerous}"
        )
        await interaction.response.send_message(embed=embed)

    # ── USERINFO ──────────────────────────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Mostra le informazioni di un utente")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def userinfo(self, interaction: discord.Interaction, membro: discord.Member = None):
        m = membro or interaction.user

        badges = [BADGES[f.name] for f in m.public_flags.all() if f.name in BADGES]
        badge_txt = " ".join(badges) if badges else "Nessuno"
        colore = str(m.color) if m.color.value else "Nessuno"
        n_warn = len(db.get_warnings(interaction.guild_id, m.id))
        ruoli = [r.mention for r in reversed(m.roles) if r.name != "@everyone"]

        embed = discord.Embed(
            title=f"Who is {m.display_name}?",
            color=m.color if m.color.value else 0x5865F2,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=m.display_avatar.url)

        embed.add_field(
            name="General Informations:",
            value=(
                f"👤 **Name:** {m.display_name}\n"
                f"﹥ **Username:** {m.name}\n"
                f"﹥ **ID:** `{m.id}`\n"
                f"🎂 **Creation:** {discord.utils.format_dt(m.created_at, 'R')}\n"
                f"📅 **Join:** {discord.utils.format_dt(m.joined_at, 'R') if m.joined_at else 'sconosciuto'}\n"
                f"🎨 **Color:** {colore}\n"
                f"🏅 **Badges:** {badge_txt}"
            ),
            inline=False,
        )

        info_mod = (
            f"⚠️ **Warn:** {n_warn}\n"
            f"🤖 **Bot:** {'Sì' if m.bot else 'No'}\n"
            f"🎭 **Ruolo più alto:** {m.top_role.mention}"
        )
        if m.is_timed_out():
            info_mod += f"\n⏱️ **In timeout fino a:** {discord.utils.format_dt(m.timed_out_until, 'R')}"
        embed.add_field(name="Moderazione:", value=info_mod, inline=False)

        if ruoli:
            embed.add_field(name=f"Ruoli ({len(ruoli)}):", value=" ".join(ruoli)[:1024], inline=False)

        await interaction.response.send_message(embed=embed)


class BanlistView(discord.ui.View):
    PER_PAGINA = 10

    def __init__(self, bans: list, autore_id: int):
        super().__init__(timeout=120)
        self.bans = bans
        self.autore_id = autore_id
        self.pagina = 0
        self.pagine_totali = (len(bans) - 1) // self.PER_PAGINA + 1
        self._aggiorna_bottoni()

    def _aggiorna_bottoni(self):
        self.prev.disabled = self.pagina == 0
        self.next.disabled = self.pagina >= self.pagine_totali - 1

    def crea_embed(self) -> discord.Embed:
        inizio = self.pagina * self.PER_PAGINA
        fetta = self.bans[inizio:inizio + self.PER_PAGINA]

        desc = ""
        for entry in fetta:
            motivo = entry.reason or "Nessun motivo"
            desc += f"**{entry.user}**\n`{entry.user.id}` • 📋 {motivo}\n\n"

        embed = discord.Embed(
            title=f"🔨 Utenti bannati ({len(self.bans)})",
            description=desc,
            color=COLORI["ban"],
        )
        embed.set_footer(text=f"Pagina {self.pagina + 1}/{self.pagine_totali}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message("❌ Solo chi ha usato il comando può sfogliare.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina -= 1
        self._aggiorna_bottoni()
        await interaction.response.edit_message(embed=self.crea_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina += 1
        self._aggiorna_bottoni()
        await interaction.response.edit_message(embed=self.crea_embed(), view=self)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
