import discord
from discord.ext import commands
import datetime
import io

import database as db
import logconfig

# Color palette
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
    return f"**[Jump to message](https://discord.com/channels/{guild_id}/{channel_id}/{message_id})**"


def _emb(color, title, first, rest=None, icon=None, user=None):
    """Embed pulito: intestazione ### per TUTTI i log, poi prima riga, riga vuota, resto.

    Con `user` mostra anche nome utente + avatar nell'header.
    """
    e = discord.Embed(color=color, timestamp=now())
    if user is not None:
        e.set_author(name=str(user), icon_url=user.display_avatar.url)
    elif icon:
        e.set_thumbnail(url=icon)
    desc = f"### {title}\n{first}"
    if rest:
        desc += "\n\n" + "\n".join(rest)
    e.description = desc
    return e


def _duration(sec: int) -> str:
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


# Persistent "Copy ID" button (DynamicItem: works even after restart)
class CopyIdButton(discord.ui.DynamicItem[discord.ui.Button], template=r"copyid:(?P<uid>\d+)"):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(discord.ui.Button(
            label="User ID", emoji="🆔",
            style=discord.ButtonStyle.secondary, custom_id=f"copyid:{user_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["uid"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"```{self.user_id}```", ephemeral=True)


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {}     # guild_id -> {code: {"uses": int, "inviter": user}}
        self.voice_since = {}      # (guild_id, user_id) -> join datetime

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
        if source_channel_id is not None:
            # source_channel_id può essere un singolo id o una lista di id
            # (es. spostamento vocale = canale di partenza + canale di arrivo).
            if isinstance(source_channel_id, (list, tuple, set)):
                ids = [c for c in source_channel_id if c]
            else:
                ids = [source_channel_id]
            blacklisted = bl.get("channels", [])
            # Se ANCHE UNO SOLO dei canali coinvolti è blacklistato, l'intero log
            # va nel canale segreto: i log generali non devono saperne nulla.
            if any(cid in blacklisted for cid in ids):
                secret = bl.get("secret_channel")
                if not secret:
                    return
                dest = guild.get_channel(secret)
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

    async def _changed_by(self, guild, action, target_id):
        """Restituisce 'mention' di chi ha fatto l'azione, o 'themselves' se è stato l'utente stesso."""
        actor, _ = await self._actor(guild, action, target_id)
        if actor is None or actor.id == target_id:
            return "themselves"
        return actor.mention

    # ── INVITES (cache to know who used / created an invite) ─────────────────
    def _snapshot(self, invites):
        return {i.code: {"uses": i.uses or 0, "inviter": i.inviter} for i in invites}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._cache_invites(guild)

    async def _cache_invites(self, guild):
        try:
            self.invite_cache[guild.id] = self._snapshot(await guild.invites())
        except discord.HTTPException:
            pass

    async def _find_invite(self, guild):
        try:
            new = await guild.invites()
        except discord.HTTPException:
            return None
        old = self.invite_cache.get(guild.id, {})
        used = None
        for inv in new:
            if (inv.uses or 0) > old.get(inv.code, {}).get("uses", 0):
                used = inv
                break
        self.invite_cache[guild.id] = self._snapshot(new)
        return used

    # ── MEMBERS ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if member.bot:
            actor, _ = await self._actor(guild, discord.AuditLogAction.bot_add, member.id)
            rest = [f"**Added by:** {actor.mention}"] if actor else []
            e = _emb(GREEN, "🤖 Bot Added", f"{member.mention} (`{member.id}`)", rest, user=member)
            await self._send(guild, "members", "bot", e, copy_id=member.id)
            return

        invite = await self._find_invite(guild)
        rest = [f"**Account created:** {discord.utils.format_dt(member.created_at, 'R')}"]
        if invite:
            inviter = invite.inviter.mention if invite.inviter else "unknown"
            rest.append(f"**Invite used:** `{invite.code}` by {inviter}")
        e = _emb(GREEN, "📥 Member Joined", f"{member.mention} (`{member.id}`)", rest, user=member)
        await self._send(guild, "members", "join", e, copy_id=member.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if member.bot:
            e = _emb(RED, "🤖 Bot Removed", f"{member} (`{member.id}`)", user=member)
            await self._send(guild, "members", "bot", e, copy_id=member.id)
            return

        actor, reason = await self._actor(guild, discord.AuditLogAction.kick, member.id)
        if actor:
            rest = [f"**Moderator:** {actor.mention}"]
            if reason:
                rest.append(f"**Reason:** {reason}")
            e = _emb(RED, "👢 Member Kicked", f"{member} (`{member.id}`)", rest, user=member)
            await self._send(guild, "modlogs", "kick", e, copy_id=member.id)
        else:
            roles = [r.mention for r in member.roles if r.name != "@everyone"]
            rest = [f"**Roles:** {' '.join(roles)[:900]}"] if roles else []
            e = _emb(RED, "📤 Member Left", f"{member} (`{member.id}`)", rest, user=member)
            await self._send(guild, "members", "leave", e, copy_id=member.id)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        actor, reason = await self._actor(guild, discord.AuditLogAction.ban, user.id)
        rest = []
        if actor:
            rest.append(f"**Moderator:** {actor.mention}")
        if reason:
            rest.append(f"**Reason:** {reason}")
        e = _emb(RED, "🔨 Member Banned", f"{user} (`{user.id}`)", rest, user=user)
        await self._send(guild, "modlogs", "ban", e, copy_id=user.id)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        actor, _ = await self._actor(guild, discord.AuditLogAction.unban, user.id)
        rest = [f"**Moderator:** {actor.mention}"] if actor else []
        e = _emb(GREEN, "✅ Member Unbanned", f"{user} (`{user.id}`)", rest, user=user)
        await self._send(guild, "modlogs", "ban", e, copy_id=user.id)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild

        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            by = await self._changed_by(guild, discord.AuditLogAction.member_role_update, after.id)
            if by == "themselves":
                by = "themselves (onboarding / channels & roles)"
            if added:
                e = _emb(GREEN, "🎭 Role Given", after.mention,
                         [f"**Roles:** {' '.join(r.mention for r in added)}", f"**By:** {by}"], user=after)
                await self._send(guild, "members", "role_given", e, copy_id=after.id)
            if removed:
                e = _emb(RED, "🎭 Role Taken", after.mention,
                         [f"**Roles:** {' '.join(r.mention for r in removed)}", f"**By:** {by}"], user=after)
                await self._send(guild, "members", "role_taken", e, copy_id=after.id)

        if before.nick != after.nick:
            by = await self._changed_by(guild, discord.AuditLogAction.member_update, after.id)
            e = _emb(ORANGE, "🏷️ Nickname Changed", after.mention,
                     [f"**Before:** {before.nick or '*none*'}",
                      f"**After:** {after.nick or '*none*'}",
                      f"**Changed by:** {by}"], user=after)
            await self._send(guild, "members", "nickname", e, copy_id=after.id)

        if before.guild_avatar != after.guild_avatar:
            e = _emb(ORANGE, "🖼️ Server Avatar Changed", after.mention, user=after)
            if after.guild_avatar:
                e.set_thumbnail(url=after.guild_avatar.url)
            await self._send(guild, "members", "avatar", e, copy_id=after.id)

        b_to = getattr(before, "timed_out_until", None)
        a_to = getattr(after, "timed_out_until", None)
        if b_to != a_to:
            if a_to:
                by = await self._changed_by(guild, discord.AuditLogAction.member_update, after.id)
                e = _emb(GOLD, "⏱️ Timeout Applied", after.mention,
                         [f"**Expires:** {discord.utils.format_dt(a_to, 'R')}", f"**By:** {by}"], user=after)
            else:
                e = _emb(GREEN, "✅ Timeout Removed", after.mention, user=after)
            await self._send(guild, "modlogs", "timeout", e, copy_id=after.id)

        if before.premium_since != after.premium_since:
            if after.premium_since and not before.premium_since:
                e = _emb(PURPLE, "✨ New Boost!", f"{after.mention} boosted the server!",
                         [f"**Total boosts:** {guild.premium_subscription_count}"], user=after)
                await self._send(guild, "server", "boost", e, copy_id=after.id)
            elif before.premium_since and not after.premium_since:
                e = _emb(RED, "💔 Boost Removed", f"{after.mention} removed their boost.",
                         [f"**Total boosts:** {guild.premium_subscription_count}"], user=after)
                await self._send(guild, "server", "boost", e, copy_id=after.id)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        """Cambio avatar del PROFILO PRINCIPALE (globale): lo logga in ogni server condiviso."""
        if before.avatar == after.avatar:
            return
        for guild in self.bot.guilds:
            if not guild.get_member(after.id):
                continue
            e = _emb(ORANGE, "🖼️ Profile Avatar Changed", after.mention, user=after)
            e.set_thumbnail(url=after.display_avatar.url)
            await self._send(guild, "members", "avatar", e, copy_id=after.id)

    # ── MESSAGES ─────────────────────────────────────────────────────────────
    async def _deleter(self, message):
        actor, _ = await self._actor(message.guild, discord.AuditLogAction.message_delete, message.author.id)
        if actor and actor.id != message.author.id:
            return actor.mention
        return f"{message.author.mention} (self)"

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or (message.author and message.author.bot):
            return

        chi = await self._deleter(message)
        rest = [f"**Channel:** {message.channel.mention}", f"**Deleted by:** {chi}"]
        if message.content:
            rest.append(f"**Content:**\n{message.content[:1500]}")
        e = _emb(RED, "🗑️ Message Deleted", f"**Author:** {message.author.mention}", rest,
                 user=message.author)
        await self._send(message.guild, "messages", "delete", e,
                         source_channel_id=message.channel.id, copy_id=message.author.id)

        if message.attachments:
            files = []
            for a in message.attachments:
                try:
                    files.append(await a.to_file(use_cached=True))
                except (discord.HTTPException, discord.NotFound):
                    pass
            nomi = "\n".join(f"[{a.filename}]({a.url})" for a in message.attachments)[:1000]
            fe = _emb(RED, "📎 Attachment Deleted", f"**Author:** {message.author.mention}",
                      [f"**Channel:** {message.channel.mention}", f"**Deleted by:** {chi}",
                       f"**Files:**\n{nomi}"], user=message.author)
            await self._send(message.guild, "messages", "attachment", fe,
                             source_channel_id=message.channel.id, copy_id=message.author.id, files=files)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return
        guild = messages[0].guild
        channel = messages[0].channel

        # File .txt con TUTTI i messaggi cancellati (cronologici).
        lines = []
        for m in sorted(messages, key=lambda x: (x.created_at or now())):
            author = f"{m.author} ({m.author.id})" if m.author else "Unknown"
            ts = (m.created_at or now()).strftime("%Y-%m-%d %H:%M:%S UTC")
            content = m.content or "[no text content]"
            extra = ""
            if m.attachments:
                extra = "\n" + "\n".join(f"[attachment] {a.url}" for a in m.attachments)
            lines.append(f"{author} @ {ts}:\n{content}{extra}\n")
        full_text = "\n".join(lines)
        buf = io.BytesIO(full_text.encode("utf-8"))
        log_file = discord.File(buf, filename="deleted_messages.txt")

        # Anteprima: primi 10 messaggi nell'embed, il resto nel file.
        preview = []
        for m in messages[:10]:
            author = m.author.mention if m.author else "Unknown"
            content = (m.content or "*[no text]*").replace("\n", " ")
            if len(content) > 80:
                content = content[:80] + "…"
            preview.append(f"**{author}:** {content}")
        if len(messages) > 10:
            preview.append(f"*…and {len(messages) - 10} more (see attached file)*")

        rest = [f"**Messages deleted:** {len(messages)}", ""] + preview
        e = _emb(RED, "🧹 Bulk Message Delete", f"**Channel:** {channel.mention}", rest)
        await self._send(guild, "messages", "bulk_delete", e,
                         source_channel_id=channel.id, files=[log_file])

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild or (after.author and after.author.bot) or before.content == after.content:
            return
        e = _emb(ORANGE, "✏️ Message Edited", f"**Author:** {after.author.mention}",
                 [f"**Channel:** {after.channel.mention}",
                  jump(after.guild.id, after.channel.id, after.id),
                  f"**Before:** {(before.content or '*empty*')[:900]}",
                  f"**After:** {(after.content or '*empty*')[:900]}"],
                 user=after.author)
        await self._send(after.guild, "messages", "edit", e,
                         source_channel_id=after.channel.id, copy_id=after.author.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not payload.guild_id or (payload.member and payload.member.bot):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        e = _emb(GREEN, "➕ Reaction Added", f"<@{payload.user_id}> reacted with {payload.emoji}",
                 [f"**Channel:** <#{payload.channel_id}>",
                  jump(payload.guild_id, payload.channel_id, payload.message_id)])
        await self._send(guild, "messages", "reaction", e,
                         source_channel_id=payload.channel_id, copy_id=payload.user_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        e = _emb(RED, "➖ Reaction Removed", f"<@{payload.user_id}> removed {payload.emoji}",
                 [f"**Channel:** <#{payload.channel_id}>",
                  jump(payload.guild_id, payload.channel_id, payload.message_id)])
        await self._send(guild, "messages", "reaction", e,
                         source_channel_id=payload.channel_id, copy_id=payload.user_id)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        e = _emb(GREEN, "🧵 Thread Created", thread.mention, [f"**Parent:** <#{thread.parent_id}>"])
        await self._send(thread.guild, "messages", "thread", e, source_channel_id=thread.parent_id)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        e = _emb(RED, "🧵 Thread Deleted", f"**{thread.name}**", [f"**Parent:** <#{thread.parent_id}>"])
        await self._send(thread.guild, "messages", "thread", e, source_channel_id=thread.parent_id)

    # Pin / Unpin (via audit log)
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        guild = entry.guild
        try:
            if entry.action == discord.AuditLogAction.message_pin:
                e = _emb(GOLD, "📌 Message Pinned", f"{entry.user.mention} pinned a message",
                         [f"**Channel:** <#{entry.extra.channel.id}>",
                          jump(guild.id, entry.extra.channel.id, entry.extra.message_id)])
                await self._send(guild, "messages", "pin", e, source_channel_id=entry.extra.channel.id)
            elif entry.action == discord.AuditLogAction.message_unpin:
                e = _emb(GREY, "📌 Message Unpinned", f"{entry.user.mention} unpinned a message",
                         [f"**Channel:** <#{entry.extra.channel.id}>",
                          jump(guild.id, entry.extra.channel.id, entry.extra.message_id)])
                await self._send(guild, "messages", "pin", e, source_channel_id=entry.extra.channel.id)
        except (AttributeError, discord.HTTPException):
            pass

    # ── VOICE ────────────────────────────────────────────────────────────────
    def _voice_channel(self, before, after):
        c = after.channel or before.channel
        return c.id if c else None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        key = (guild.id, member.id)

        if before.channel != after.channel:
            if before.channel is None:
                self.voice_since[key] = now()
                e = _emb(GREEN, "🔊 Voice Channel Joined",
                         f"{member.mention} **joined** {after.channel.mention}", user=member)
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=after.channel.id, copy_id=member.id)
            elif after.channel is None:
                t = self.voice_since.pop(key, None)
                actor, _ = await self._actor(guild, discord.AuditLogAction.member_disconnect)
                rest = []
                if t:
                    rest.append(f"**Session:** joined {discord.utils.format_dt(t, 'R')} • stayed **{_duration(int((now()-t).total_seconds()))}**")
                if actor and actor.id != member.id:
                    e = _emb(RED, "🔌 Disconnected from Voice",
                             f"{member.mention} was **disconnected** from {before.channel.mention} by {actor.mention}",
                             rest, user=member)
                else:
                    e = _emb(RED, "🔊 Voice Channel Left",
                             f"{member.mention} **left** {before.channel.mention}", rest, user=member)
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=before.channel.id, copy_id=member.id)
            else:
                t = self.voice_since.get(key)
                self.voice_since[key] = now()
                rest = []
                if t:
                    rest.append(f"**Previous session:** **{_duration(int((now()-t).total_seconds()))}**")
                e = _emb(BLUE, "🔀 Voice Channel Moved",
                         f"{member.mention} **moved** from {before.channel.mention} to {after.channel.mention}",
                         rest, user=member)
                await self._send(guild, "voice", "join_leave", e,
                                 source_channel_id=[before.channel.id, after.channel.id],
                                 copy_id=member.id)

        # Mute / Deafen — deafen has priority (deafening auto-mutes)
        md = []
        if before.self_deaf != after.self_deaf:
            md.append("🔈 Deafened" if after.self_deaf else "🔊 Undeafened")
        elif before.self_mute != after.self_mute:
            md.append("🔇 Muted" if after.self_mute else "🎙️ Unmuted")
        if before.deaf != after.deaf:
            md.append("🔈 Server Deafened" if after.deaf else "🔊 Server Undeafened")
        elif before.mute != after.mute:
            md.append("🔇 Server Muted" if after.mute else "🎙️ Server Unmuted")
        if md:
            e = _emb(ORANGE, "🎙️ Voice State", member.mention, md, user=member)
            await self._send(guild, "voice", "mute_deaf", e,
                             source_channel_id=self._voice_channel(before, after), copy_id=member.id)

        # Stream / Video
        sv = []
        if before.self_stream != after.self_stream:
            sv.append("🔴 Started streaming" if after.self_stream else "⚫ Stopped streaming")
        if before.self_video != after.self_video:
            sv.append("📷 Camera on" if after.self_video else "📷 Camera off")
        if sv:
            e = _emb(PURPLE, "📺 Stream / Video", member.mention, sv, user=member)
            await self._send(guild, "voice", "stream_video", e,
                             source_channel_id=self._voice_channel(before, after), copy_id=member.id)

    # ── CHANNELS ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        e = _emb(GREEN, "📁 Channel Created", f"{channel.mention} (`{channel.id}`)")
        await self._send(channel.guild, "channels", "create", e)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        e = _emb(RED, "📁 Channel Deleted", f"**{channel.name}** (`{channel.id}`)")
        await self._send(channel.guild, "channels", "delete", e)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            changes.append("**Topic** changed")
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            changes.append(f"**NSFW:** {getattr(after, 'nsfw', None)}")
        if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
            changes.append(f"**Slowmode:** {getattr(after, 'slowmode_delay', 0)}s")
        if changes:
            e = _emb(ORANGE, "📁 Channel Updated", after.mention, changes)
            await self._send(after.guild, "channels", "update", e, source_channel_id=after.id)

        if before.overwrites != after.overwrites:
            lines = []
            for target in set(before.overwrites) | set(after.overwrites):
                bo = before.overwrites.get(target)
                ao = after.overwrites.get(target)
                if bo == ao:
                    continue
                diff = self._perm_diff(bo, ao)
                if diff:
                    nome = target.mention if hasattr(target, "mention") else str(target)
                    lines.append(f"**{nome}:**\n" + "\n".join(diff))
            e = _emb(ORANGE, "🔐 Channel Permissions Updated", after.mention, lines[:12] or None)
            await self._send(after.guild, "channels", "permissions", e, source_channel_id=after.id)

    @staticmethod
    def _perm_diff(before_ow, after_ow):
        b = dict(before_ow) if before_ow else {}
        a = dict(after_ow) if after_ow else {}
        out = []
        for perm in set(b) | set(a):
            if b.get(perm) != a.get(perm):
                val = a.get(perm)
                sym = "✅" if val is True else ("❌" if val is False else "➖")
                out.append(f"{sym} {perm.replace('_', ' ')}")
        return out

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        e = _emb(ORANGE, "🪝 Webhooks Updated",
                 f"Webhooks in {channel.mention} changed (created / deleted / modified).")
        await self._send(channel.guild, "channels", "webhook", e, source_channel_id=channel.id)

    # ── ROLES ────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        e = _emb(GREEN, "🎭 Role Created", f"{role.mention} (`{role.id}`)")
        await self._send(role.guild, "roles", "create", e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        e = _emb(RED, "🎭 Role Deleted", f"**{role.name}** (`{role.id}`)")
        await self._send(role.guild, "roles", "delete", e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"**Color:** {before.color} → {after.color}")
        if before.permissions != after.permissions:
            changes.append("**Permissions** changed")
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** {after.hoist}")
        if not changes:
            return
        e = _emb(ORANGE, "🎭 Role Updated", after.mention, changes)
        await self._send(after.guild, "roles", "update", e)

    # ── SERVER ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("**Icon** changed")
        if before.owner_id != after.owner_id:
            changes.append(f"**Owner:** <@{before.owner_id}> → <@{after.owner_id}>")
        if not changes:
            return
        e = _emb(ORANGE, "🛠️ Server Updated", changes[0], changes[1:])
        if before.icon != after.icon and after.icon:
            e.set_thumbnail(url=after.icon.url)
        await self._send(after, "server", "update", e)

    # ── ACTIONS ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = {
            "uses": invite.uses or 0, "inviter": invite.inviter}
        rest = []
        if invite.inviter:
            rest.append(f"**Created by:** {invite.inviter.mention}")
        if invite.max_uses:
            rest.append(f"**Max uses:** {invite.max_uses}")
        e = _emb(BLUE, "✉️ Invite Created", f"**Code:** `{invite.code}`", rest)
        await self._send(invite.guild, "actions", "invite_create", e)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        cached = self.invite_cache.get(invite.guild.id, {}).pop(invite.code, None)
        rest = []
        if cached and cached.get("inviter"):
            rest.append(f"**Originally created by:** {cached['inviter'].mention}")
        e = _emb(RED, "✉️ Invite Deleted", f"**Code:** `{invite.code}`", rest)
        await self._send(invite.guild, "actions", "invite_delete", e)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        prev = {e.id for e in before}
        curr = {e.id for e in after}
        for emo in [e for e in after if e.id not in prev]:
            e = _emb(GREEN, "😀 Emoji Created", f"{emo} `:{emo.name}:`")
            await self._send(guild, "actions", "emoji", e)
        for emo in [e for e in before if e.id not in curr]:
            e = _emb(RED, "😀 Emoji Deleted", f"`:{emo.name}:`")
            await self._send(guild, "actions", "emoji", e)
        names = {e.id: e.name for e in before}
        for emo in after:
            if emo.id in names and names[emo.id] != emo.name:
                e = _emb(ORANGE, "😀 Emoji Renamed", f"{emo} `:{names[emo.id]}:` → `:{emo.name}:`")
                await self._send(guild, "actions", "emoji", e)

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event):
        e = _emb(GREEN, "📅 Event Created", f"**{event.name}**")
        await self._send(event.guild, "actions", "event", e)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event):
        e = _emb(RED, "📅 Event Deleted", f"**{event.name}**")
        await self._send(event.guild, "actions", "event", e)

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before, after):
        e = _emb(ORANGE, "📅 Event Updated", f"**{after.name}**")
        await self._send(after.guild, "actions", "event", e)


async def setup(bot):
    await bot.add_cog(Logs(bot))
