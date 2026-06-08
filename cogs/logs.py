import discord
from discord.ext import commands
import datetime

import database as db
import logconfig

# Palette colori
GREEN = 0x2ECC71
RED = 0xE74C3C
ORANGE = 0xE67E22
BLUE = 0x3498DB
GOLD = 0xF1C40F
PURPLE = 0x9B59B6
GREY = 0x95A5A6


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def jump(guild_id, channel_id, message_id):
    return f"**[Vai al messaggio](https://discord.com/channels/{guild_id}/{channel_id}/{message_id})**"


def _emb(color, titolo, icon=None):
    e = discord.Embed(color=color, timestamp=now())
    e.set_author(name=titolo, icon_url=icon)
    return e


def _durata(sec: int) -> str:
    if sec < 60:
        return f"{sec} sec"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min {s} sec"
    h, m = divmod(m, 60)
    return f"{h}h {m} min"


# Pulsante persistente "Copia ID" (DynamicItem: funziona anche dopo riavvio)
class CopyIdButton(discord.ui.DynamicItem[discord.ui.Button], template=r"copyid:(?P<uid>\d+)"):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(discord.ui.Button(
            label="ID utente", emoji="🆔",
            style=discord.ButtonStyle.secondary, custom_id=f"copyid:{user_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["uid"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🆔 ID utente:\n```{self.user_id}```", ephemeral=True)


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {}     # guild_id -> {code: uses}
        self.voice_since = {}      # (guild_id, user_id) -> datetime di ingresso in voce

    async def cog_load(self):
        self.bot.add_dynamic_items(CopyIdButton)

    # ── UTILITY ─────────────────────────────────────────────────────────────
    async def _send(self, guild, category, event, embed, source_channel_id=None, copy_id=None, files=None):
        if guild is None:
            return
        config = db.get_log_config(guild.id)
        if not logconfig.is_enabled(config, category, event):
            return

        bl = config.get("log_blacklist", {})
        dest = None
        if source_channel_id and source_channel_id in bl.get("channels", []):
            segreto = bl.get("secret_channel")
            if not segreto:
                return
            dest = guild.get_channel(segreto)
            if not dest:
                return

        ch = dest or guild.get_channel(logconfig.get_channel_id(config, category))
        if not ch:
            return

        view = None
        if copy_id:
            view = discord.ui.View(timeout=None)
            view.add_item(CopyIdButton(copy_id))
        try:
            await ch.send(embed=embed, view=view, files=files or [])
        except discord.HTTPException:
            pass

    async def _actor(self, guild, action, target_id=None):
        try:
            async for entry in guild.audit_logs(limit=6, action=action):
                if target_id is None or (entry.target and entry.target.id == target_id):
                    if (now() - entry.created_at).total_seconds() < 12:
                        return entry.user, entry.reason
        except (discord.Forbidden, discord.HTTPException):
            pass
        return None, None

    # ── INVITI (cache per sapere quale invito usa chi entra) ─────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._cache_invites(guild)

    async def _cache_invites(self, guild):
        try:
            self.invite_cache[guild.id] = {i.code: i.uses for i in await guild.invites()}
        except discord.HTTPException:
            pass

    async def _trova_invito(self, guild):
        try:
            nuovi = await guild.invites()
        except discord.HTTPException:
            return None
        vecchi = self.invite_cache.get(guild.id, {})
        usato = None
        for inv in nuovi:
            if (inv.uses or 0) > vecchi.get(inv.code, 0):
                usato = inv
                break
        self.invite_cache[guild.id] = {i.code: i.uses for i in nuovi}
        return usato

    # ── MEMBERS ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if member.bot:
            actor, _ = await self._actor(guild, discord.AuditLogAction.bot_add, member.id)
            e = _emb(GREEN, "🤖 Bot aggiunto", member.display_avatar.url)
            e.description = f"{member.mention} (`{member.id}`)"
            if actor:
                e.add_field(name="Aggiunto da", value=actor.mention, inline=False)
            await self._send(guild, "members", "bot", e, copy_id=member.id)
            return

        invito = await self._trova_invito(guild)
        e = _emb(GREEN, "📥 Membro entrato", member.display_avatar.url)
        e.description = f"{member.mention} (`{member.id}`)"
        e.add_field(name="Account creato", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        if invito:
            inviter = invito.inviter.mention if invito.inviter else "sconosciuto"
            e.add_field(name="Invito usato", value=f"`{invito.code}` da {inviter}", inline=True)
        await self._send(guild, "members", "join", e, copy_id=member.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if member.bot:
            e = _emb(RED, "🤖 Bot rimosso", member.display_avatar.url)
            e.description = f"{member} (`{member.id}`)"
            await self._send(guild, "members", "bot", e, copy_id=member.id)
            return

        actor, reason = await self._actor(guild, discord.AuditLogAction.kick, member.id)
        if actor:
            e = _emb(RED, "👢 Membro kickato", member.display_avatar.url)
            e.description = f"{member} (`{member.id}`)"
            e.add_field(name="Moderatore", value=actor.mention, inline=True)
            if reason:
                e.add_field(name="Motivo", value=reason, inline=True)
            await self._send(guild, "modlogs", "kick", e, copy_id=member.id)
        else:
            e = _emb(RED, "📤 Membro uscito", member.display_avatar.url)
            e.description = f"{member} (`{member.id}`)"
            ruoli = [r.mention for r in member.roles if r.name != "@everyone"]
            if ruoli:
                e.add_field(name="Ruoli", value=" ".join(ruoli)[:1024], inline=False)
            await self._send(guild, "members", "leave", e, copy_id=member.id)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        actor, reason = await self._actor(guild, discord.AuditLogAction.ban, user.id)
        e = _emb(RED, "🔨 Membro bannato", user.display_avatar.url)
        e.description = f"{user} (`{user.id}`)"
        if actor:
            e.add_field(name="Moderatore", value=actor.mention, inline=True)
        if reason:
            e.add_field(name="Motivo", value=reason, inline=True)
        await self._send(guild, "modlogs", "ban", e, copy_id=user.id)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        actor, _ = await self._actor(guild, discord.AuditLogAction.unban, user.id)
        e = _emb(GREEN, "✅ Membro sbannato", user.display_avatar.url)
        e.description = f"{user} (`{user.id}`)"
        if actor:
            e.add_field(name="Moderatore", value=actor.mention, inline=True)
        await self._send(guild, "modlogs", "ban", e, copy_id=user.id)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild

        if before.roles != after.roles:
            aggiunti = [r for r in after.roles if r not in before.roles]
            rimossi = [r for r in before.roles if r not in after.roles]
            actor, _ = await self._actor(guild, discord.AuditLogAction.member_role_update, after.id)
            autore = "se stesso (onboarding / canali & ruoli)" if (actor is None or actor.id == after.id) else actor.mention
            if aggiunti:
                e = _emb(GREEN, "🎭 Ruolo assegnato", after.display_avatar.url)
                e.description = f"{after.mention}\n➕ {' '.join(r.mention for r in aggiunti)}\n👮 Da: {autore}"
                await self._send(guild, "members", "role_given", e, copy_id=after.id)
            if rimossi:
                e = _emb(RED, "🎭 Ruolo rimosso", after.display_avatar.url)
                e.description = f"{after.mention}\n➖ {' '.join(r.mention for r in rimossi)}\n👮 Da: {autore}"
                await self._send(guild, "members", "role_taken", e, copy_id=after.id)

        if before.nick != after.nick:
            e = _emb(ORANGE, "🏷️ Nickname cambiato", after.display_avatar.url)
            e.description = (f"{after.mention}\n**Prima:** {before.nick or '*nessuno*'}\n"
                            f"**Dopo:** {after.nick or '*nessuno*'}")
            await self._send(guild, "members", "nickname", e, copy_id=after.id)

        if before.guild_avatar != after.guild_avatar:
            e = _emb(ORANGE, "🖼️ Avatar server cambiato", after.display_avatar.url)
            e.description = f"{after.mention}"
            if after.guild_avatar:
                e.set_thumbnail(url=after.guild_avatar.url)
            await self._send(guild, "members", "avatar", e, copy_id=after.id)

        b_to = getattr(before, "timed_out_until", None)
        a_to = getattr(after, "timed_out_until", None)
        if b_to != a_to:
            if a_to:
                e = _emb(GOLD, "⏱️ Timeout applicato", after.display_avatar.url)
                e.description = f"{after.mention}\nScade {discord.utils.format_dt(a_to, 'R')}"
            else:
                e = _emb(GREEN, "✅ Timeout rimosso", after.display_avatar.url)
                e.description = f"{after.mention}"
            await self._send(guild, "modlogs", "timeout", e, copy_id=after.id)

        if before.premium_since != after.premium_since:
            if after.premium_since and not before.premium_since:
                e = _emb(PURPLE, "✨ Nuovo Boost!", after.display_avatar.url)
                e.description = f"{after.mention} ha boostato il server!\nBoost totali: {guild.premium_subscription_count}"
                await self._send(guild, "server", "boost", e, copy_id=after.id)
            elif before.premium_since and not after.premium_since:
                e = _emb(RED, "💔 Boost rimosso", after.display_avatar.url)
                e.description = f"{after.mention} ha tolto il boost.\nBoost totali: {guild.premium_subscription_count}"
                await self._send(guild, "server", "boost", e, copy_id=after.id)

    # ── MESSAGES ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or (message.author and message.author.bot):
            return

        e = _emb(RED, "🗑️ Messaggio cancellato", message.author.display_avatar.url)
        e.description = f"**Autore:** {message.author.mention}\n**Canale:** {message.channel.mention}"
        if message.content:
            e.add_field(name="Contenuto", value=message.content[:1024], inline=False)
        await self._send(message.guild, "messages", "delete", e,
                         source_channel_id=message.channel.id, copy_id=message.author.id)

        if message.attachments:
            files = []
            for a in message.attachments:
                try:
                    files.append(await a.to_file(use_cached=True))
                except (discord.HTTPException, discord.NotFound):
                    pass
            fe = _emb(RED, "📎 Allegato cancellato", message.author.display_avatar.url)
            fe.description = (f"**Autore:** {message.author.mention}\n"
                             f"**Canale:** {message.channel.mention}\n"
                             f"**File:** " + ", ".join(f"`{a.filename}`" for a in message.attachments)[:900])
            await self._send(message.guild, "messages", "attachment", fe,
                             source_channel_id=message.channel.id, copy_id=message.author.id, files=files)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return
        e = _emb(RED, "🧹 Cancellazione multipla")
        e.description = f"**Canale:** {messages[0].channel.mention}\n**Messaggi eliminati:** {len(messages)}"
        await self._send(messages[0].guild, "messages", "bulk_delete", e,
                         source_channel_id=messages[0].channel.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild or (after.author and after.author.bot) or before.content == after.content:
            return
        e = _emb(ORANGE, "✏️ Messaggio modificato", after.author.display_avatar.url)
        e.description = f"**Autore:** {after.author.mention}\n**Canale:** {after.channel.mention}\n{jump(after.guild.id, after.channel.id, after.id)}"
        e.add_field(name="Prima", value=(before.content or "*vuoto*")[:1024], inline=False)
        e.add_field(name="Dopo", value=(after.content or "*vuoto*")[:1024], inline=False)
        await self._send(after.guild, "messages", "edit", e,
                         source_channel_id=after.channel.id, copy_id=after.author.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not payload.guild_id or (payload.member and payload.member.bot):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        e = _emb(GREEN, "➕ Reazione aggiunta")
        e.description = (f"<@{payload.user_id}> ha reagito con {payload.emoji} in <#{payload.channel_id}>\n"
                        f"{jump(payload.guild_id, payload.channel_id, payload.message_id)}")
        await self._send(guild, "messages", "reaction", e,
                         source_channel_id=payload.channel_id, copy_id=payload.user_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        e = _emb(RED, "➖ Reazione rimossa")
        e.description = (f"<@{payload.user_id}> ha tolto {payload.emoji} in <#{payload.channel_id}>\n"
                        f"{jump(payload.guild_id, payload.channel_id, payload.message_id)}")
        await self._send(guild, "messages", "reaction", e,
                         source_channel_id=payload.channel_id, copy_id=payload.user_id)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        e = _emb(GREEN, "🧵 Thread creato")
        e.description = f"{thread.mention} in <#{thread.parent_id}>"
        await self._send(thread.guild, "messages", "thread", e, source_channel_id=thread.parent_id)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        e = _emb(RED, "🧵 Thread eliminato")
        e.description = f"**{thread.name}** (era in <#{thread.parent_id}>)"
        await self._send(thread.guild, "messages", "thread", e, source_channel_id=thread.parent_id)

    # Pin / Unpin (via audit log)
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        guild = entry.guild
        if entry.action == discord.AuditLogAction.message_pin:
            e = _emb(GOLD, "📌 Messaggio fissato")
            e.description = (f"{entry.user.mention} ha fissato un messaggio in <#{entry.extra.channel.id}>\n"
                            f"{jump(guild.id, entry.extra.channel.id, entry.extra.message_id)}")
            await self._send(guild, "messages", "pin", e, source_channel_id=entry.extra.channel.id)
        elif entry.action == discord.AuditLogAction.message_unpin:
            e = _emb(GREY, "📌 Messaggio rimosso dai fissati")
            e.description = (f"{entry.user.mention} ha rimosso un messaggio dai fissati in <#{entry.extra.channel.id}>\n"
                            f"{jump(guild.id, entry.extra.channel.id, entry.extra.message_id)}")
            await self._send(guild, "messages", "pin", e, source_channel_id=entry.extra.channel.id)

    # ── VOICE ────────────────────────────────────────────────────────────────
    def _voce_canale(self, before, after):
        c = after.channel or before.channel
        return c.id if c else None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        key = (guild.id, member.id)

        # Join / Leave / Move (con durata)
        if before.channel != after.channel:
            if before.channel is None:
                self.voice_since[key] = now()
                e = _emb(GREEN, "🔊 Entrato in vocale", member.display_avatar.url)
                e.description = f"{member.mention} è entrato in **{after.channel.name}**"
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=after.channel.id, copy_id=member.id)
            elif after.channel is None:
                t = self.voice_since.pop(key, None)
                actor, _ = await self._actor(guild, discord.AuditLogAction.member_disconnect)
                if actor and actor.id != member.id:
                    e = _emb(RED, "🔌 Disconnesso dalla voce", member.display_avatar.url)
                    e.description = f"{member.mention} disconnesso da **{before.channel.name}** da {actor.mention}"
                else:
                    e = _emb(RED, "🔊 Uscito dalla voce", member.display_avatar.url)
                    e.description = f"{member.mention} è uscito da **{before.channel.name}**"
                if t:
                    e.add_field(name="Permanenza",
                                value=f"entrato {discord.utils.format_dt(t, 'R')} • rimasto **{_durata(int((now()-t).total_seconds()))}**",
                                inline=False)
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=before.channel.id, copy_id=member.id)
            else:
                t = self.voice_since.get(key)
                self.voice_since[key] = now()
                e = _emb(BLUE, "🔀 Spostato di vocale", member.display_avatar.url)
                e.description = f"{member.mention}: **{before.channel.name}** → **{after.channel.name}**"
                if t:
                    e.add_field(name="Permanenza precedente",
                                value=f"**{_durata(int((now()-t).total_seconds()))}**", inline=False)
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=after.channel.id, copy_id=member.id)

        # Mute / Deaf
        md = []
        if before.self_mute != after.self_mute:
            md.append("🔇 si è mutato" if after.self_mute else "🎙️ si è smutato")
        if before.self_deaf != after.self_deaf:
            md.append("🔈 si è sordinato" if after.self_deaf else "🔊 si è desordinato")
        if before.mute != after.mute:
            md.append("🔇 mutato dal server" if after.mute else "🔊 smutato dal server")
        if before.deaf != after.deaf:
            md.append("🔈 sordinato dal server" if after.deaf else "🔊 desordinato dal server")
        if md:
            e = _emb(ORANGE, "🎙️ Stato audio", member.display_avatar.url)
            e.description = f"{member.mention}\n" + "\n".join(md)
            await self._send(guild, "voice", "mute_deaf", e,
                             source_channel_id=self._voce_canale(before, after), copy_id=member.id)

        # Stream / Video
        sv = []
        if before.self_stream != after.self_stream:
            sv.append("🔴 ha iniziato lo streaming" if after.self_stream else "⚫ ha terminato lo streaming")
        if before.self_video != after.self_video:
            sv.append("📷 ha acceso la camera" if after.self_video else "📷 ha spento la camera")
        if sv:
            e = _emb(PURPLE, "📺 Stream / Video", member.display_avatar.url)
            e.description = f"{member.mention}\n" + "\n".join(sv)
            await self._send(guild, "voice", "stream_video", e,
                             source_channel_id=self._voce_canale(before, after), copy_id=member.id)

    # ── CHANNELS ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        e = _emb(GREEN, "📁 Canale creato")
        e.description = f"{channel.mention} (`{channel.id}`)"
        await self._send(channel.guild, "channels", "create", e)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        e = _emb(RED, "📁 Canale eliminato")
        e.description = f"**{channel.name}** (`{channel.id}`)"
        await self._send(channel.guild, "channels", "delete", e)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        cambi = []
        if before.name != after.name:
            cambi.append(f"**Nome:** {before.name} → {after.name}")
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            cambi.append("**Topic** modificato")
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            cambi.append(f"**NSFW:** {getattr(after, 'nsfw', None)}")
        if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
            cambi.append(f"**Slowmode:** {getattr(after, 'slowmode_delay', 0)}s")
        if cambi:
            e = _emb(ORANGE, "📁 Canale modificato")
            e.description = f"{after.mention}\n" + "\n".join(cambi)
            await self._send(after.guild, "channels", "update", e, source_channel_id=after.id)

        if before.overwrites != after.overwrites:
            e = _emb(ORANGE, "🔐 Permessi canale modificati")
            e.description = f"I permessi di {after.mention} sono cambiati."
            await self._send(after.guild, "channels", "permissions", e, source_channel_id=after.id)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        e = _emb(ORANGE, "🪝 Webhook aggiornati")
        e.description = f"I webhook di {channel.mention} sono cambiati (creato / eliminato / modificato)."
        await self._send(channel.guild, "channels", "webhook", e, source_channel_id=channel.id)

    # ── ROLES ────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        e = _emb(GREEN, "🎭 Ruolo creato")
        e.description = f"{role.mention} (`{role.id}`)"
        await self._send(role.guild, "roles", "create", e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        e = _emb(RED, "🎭 Ruolo eliminato")
        e.description = f"**{role.name}** (`{role.id}`)"
        await self._send(role.guild, "roles", "delete", e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        cambi = []
        if before.name != after.name:
            cambi.append(f"**Nome:** {before.name} → {after.name}")
        if before.color != after.color:
            cambi.append(f"**Colore:** {before.color} → {after.color}")
        if before.permissions != after.permissions:
            cambi.append("**Permessi** modificati")
        if before.hoist != after.hoist:
            cambi.append(f"**Mostrato separato:** {after.hoist}")
        if not cambi:
            return
        e = _emb(ORANGE, "🎭 Ruolo modificato", )
        e.description = f"{after.mention}\n" + "\n".join(cambi)
        await self._send(after.guild, "roles", "update", e)

    # ── SERVER ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        cambi = []
        if before.name != after.name:
            cambi.append(f"**Nome:** {before.name} → {after.name}")
        if before.icon != after.icon:
            cambi.append("**Icona** cambiata")
        if before.owner_id != after.owner_id:
            cambi.append(f"**Proprietario:** <@{before.owner_id}> → <@{after.owner_id}>")
        if not cambi:
            return
        e = _emb(ORANGE, "🛠️ Server modificato")
        e.description = "\n".join(cambi)
        if before.icon != after.icon and after.icon:
            e.set_thumbnail(url=after.icon.url)
        await self._send(after, "server", "update", e)

    # ── ACTIONS ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0
        e = _emb(BLUE, "✉️ Invito creato")
        if invite.inviter:
            e.description = f"Creato da {invite.inviter.mention}"
        e.add_field(name="Codice", value=f"`{invite.code}`", inline=True)
        if invite.max_uses:
            e.add_field(name="Usi massimi", value=str(invite.max_uses), inline=True)
        await self._send(invite.guild, "actions", "invite_create", e)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        self.invite_cache.get(invite.guild.id, {}).pop(invite.code, None)
        e = _emb(RED, "✉️ Invito eliminato")
        e.description = f"Codice `{invite.code}` eliminato."
        await self._send(invite.guild, "actions", "invite_delete", e)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        prima = {e.id for e in before}
        dopo = {e.id for e in after}
        for emo in [e for e in after if e.id not in prima]:
            e = _emb(GREEN, "😀 Emoji creata")
            e.description = f"{emo} `:{emo.name}:`"
            await self._send(guild, "actions", "emoji", e)
        for emo in [e for e in before if e.id not in dopo]:
            e = _emb(RED, "😀 Emoji eliminata")
            e.description = f"`:{emo.name}:`"
            await self._send(guild, "actions", "emoji", e)
        nomi = {e.id: e.name for e in before}
        for emo in after:
            if emo.id in nomi and nomi[emo.id] != emo.name:
                e = _emb(ORANGE, "😀 Emoji rinominata")
                e.description = f"{emo} `:{nomi[emo.id]}:` → `:{emo.name}:`"
                await self._send(guild, "actions", "emoji", e)

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event):
        e = _emb(GREEN, "📅 Evento creato")
        e.description = f"**{event.name}**"
        await self._send(event.guild, "actions", "event", e)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event):
        e = _emb(RED, "📅 Evento eliminato")
        e.description = f"**{event.name}**"
        await self._send(event.guild, "actions", "event", e)

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before, after):
        e = _emb(ORANGE, "📅 Evento modificato")
        e.description = f"**{after.name}**"
        await self._send(after.guild, "actions", "event", e)


async def setup(bot):
    await bot.add_cog(Logs(bot))
