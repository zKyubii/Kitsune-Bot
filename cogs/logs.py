import discord
from discord.ext import commands
import datetime

import database as db
import logconfig

# Colori
GREEN = 0x2ECC71
RED = 0xE74C3C
ORANGE = 0xE67E22
BLUE = 0x3498DB
GOLD = 0xF1C40F
PURPLE = 0x9B59B6


def now():
    return datetime.datetime.now(datetime.timezone.utc)


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send(self, guild: discord.Guild, category: str, event: str, embed: discord.Embed):
        if guild is None:
            return
        config = db.get_log_config(guild.id)
        if not logconfig.is_enabled(config, category, event):
            return
        ch = guild.get_channel(logconfig.get_channel_id(config, category))
        if ch:
            try:
                await ch.send(embed=embed)
            except discord.HTTPException:
                pass

    async def _actor(self, guild, action, target_id=None):
        """Cerca nell'audit log chi ha eseguito un'azione (entro 10s)."""
        try:
            async for entry in guild.audit_logs(limit=6, action=action):
                if target_id is None or (entry.target and entry.target.id == target_id):
                    if (now() - entry.created_at).total_seconds() < 10:
                        return entry.user, entry.reason
        except (discord.Forbidden, discord.HTTPException):
            pass
        return None, None

    # ── MESSAGE ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or (message.author and message.author.bot):
            return
        e = discord.Embed(title="🗑️ Messaggio cancellato", color=RED, timestamp=now())
        e.add_field(name="Autore", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        e.add_field(name="Canale", value=message.channel.mention, inline=False)
        if message.content:
            e.add_field(name="Contenuto", value=message.content[:1024], inline=False)
        e.set_thumbnail(url=message.author.display_avatar.url)
        await self._send(message.guild, "message", "delete", e)

        if message.attachments:
            fe = discord.Embed(title="📎 File cancellato", color=RED, timestamp=now())
            fe.add_field(name="Autore", value=f"{message.author.mention}", inline=False)
            fe.add_field(name="Canale", value=message.channel.mention, inline=False)
            fe.add_field(name="File", value="\n".join(a.filename for a in message.attachments)[:1024], inline=False)
            await self._send(message.guild, "file", "delete", fe)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        if not messages or not messages[0].guild:
            return
        e = discord.Embed(title="🧹 Cancellazione multipla", color=RED, timestamp=now())
        e.add_field(name="Canale", value=messages[0].channel.mention, inline=True)
        e.add_field(name="Messaggi eliminati", value=str(len(messages)), inline=True)
        await self._send(messages[0].guild, "message", "bulk_delete", e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild or (after.author and after.author.bot):
            return
        if before.content == after.content:
            return
        e = discord.Embed(title="✏️ Messaggio modificato", color=ORANGE, timestamp=now())
        e.add_field(name="Autore", value=f"{after.author.mention} (`{after.author.id}`)", inline=False)
        e.add_field(name="Canale", value=after.channel.mention, inline=False)
        e.add_field(name="Prima", value=(before.content or "*vuoto*")[:1024], inline=False)
        e.add_field(name="Dopo", value=(after.content or "*vuoto*")[:1024], inline=False)
        e.add_field(name="Link", value=f"[Vai al messaggio]({after.jump_url})", inline=False)
        e.set_thumbnail(url=after.author.display_avatar.url)
        await self._send(after.guild, "message", "edit", e)

    # ── MEMBER ────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        e = discord.Embed(title="📥 Membro entrato", color=GREEN, timestamp=now())
        e.add_field(name="Utente", value=f"{member.mention} (`{member.id}`)", inline=False)
        e.add_field(name="Account creato", value=discord.utils.format_dt(member.created_at, "R"), inline=False)
        e.add_field(name="Membri totali", value=str(member.guild.member_count), inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        await self._send(member.guild, "member", "join_leave", e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        actor, reason = await self._actor(member.guild, discord.AuditLogAction.kick, member.id)
        if actor:
            e = discord.Embed(title="👢 Membro kickato", color=RED, timestamp=now())
            e.add_field(name="Utente", value=f"{member.mention} (`{member.id}`)", inline=False)
            e.add_field(name="Moderatore", value=actor.mention, inline=False)
            if reason:
                e.add_field(name="Motivo", value=reason, inline=False)
            e.set_thumbnail(url=member.display_avatar.url)
            await self._send(member.guild, "member", "kick", e)
        else:
            e = discord.Embed(title="📤 Membro uscito", color=RED, timestamp=now())
            e.add_field(name="Utente", value=f"{member} (`{member.id}`)", inline=False)
            ruoli = [r.mention for r in member.roles if r.name != "@everyone"]
            if ruoli:
                e.add_field(name="Ruoli", value=" ".join(ruoli)[:1024], inline=False)
            e.set_thumbnail(url=member.display_avatar.url)
            await self._send(member.guild, "member", "join_leave", e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        actor, reason = await self._actor(guild, discord.AuditLogAction.ban, user.id)
        e = discord.Embed(title="🔨 Membro bannato", color=RED, timestamp=now())
        e.add_field(name="Utente", value=f"{user} (`{user.id}`)", inline=False)
        if actor:
            e.add_field(name="Moderatore", value=actor.mention, inline=False)
        if reason:
            e.add_field(name="Motivo", value=reason, inline=False)
        e.set_thumbnail(url=user.display_avatar.url)
        await self._send(guild, "member", "ban", e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        actor, reason = await self._actor(guild, discord.AuditLogAction.unban, user.id)
        e = discord.Embed(title="✅ Membro sbannato", color=GREEN, timestamp=now())
        e.add_field(name="Utente", value=f"{user} (`{user.id}`)", inline=False)
        if actor:
            e.add_field(name="Moderatore", value=actor.mention, inline=False)
        e.set_thumbnail(url=user.display_avatar.url)
        await self._send(guild, "member", "ban", e)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild

        # Ruoli
        if before.roles != after.roles:
            aggiunti = [r for r in after.roles if r not in before.roles]
            rimossi = [r for r in before.roles if r not in after.roles]
            e = discord.Embed(title="🎭 Ruoli aggiornati", color=ORANGE, timestamp=now())
            e.add_field(name="Utente", value=f"{after.mention} (`{after.id}`)", inline=False)
            if aggiunti:
                e.add_field(name="➕ Aggiunti", value=" ".join(r.mention for r in aggiunti)[:1024], inline=False)
            if rimossi:
                e.add_field(name="➖ Rimossi", value=" ".join(r.mention for r in rimossi)[:1024], inline=False)
            await self._send(guild, "member", "role", e)

        # Nickname
        if before.nick != after.nick:
            e = discord.Embed(title="🏷️ Nickname cambiato", color=ORANGE, timestamp=now())
            e.add_field(name="Utente", value=f"{after.mention} (`{after.id}`)", inline=False)
            e.add_field(name="Prima", value=before.nick or "*nessuno*", inline=True)
            e.add_field(name="Dopo", value=after.nick or "*nessuno*", inline=True)
            await self._send(guild, "member", "nickname", e)

        # Timeout
        b_to = getattr(before, "timed_out_until", None)
        a_to = getattr(after, "timed_out_until", None)
        if b_to != a_to:
            if a_to:
                e = discord.Embed(title="⏱️ Timeout applicato", color=GOLD, timestamp=now())
                e.add_field(name="Scade", value=discord.utils.format_dt(a_to, "R"), inline=False)
            else:
                e = discord.Embed(title="✅ Timeout rimosso", color=GREEN, timestamp=now())
            e.add_field(name="Utente", value=f"{after.mention} (`{after.id}`)", inline=False)
            await self._send(guild, "member", "timeout", e)

        # Boost
        if before.premium_since != after.premium_since and after.premium_since and not before.premium_since:
            e = discord.Embed(title="✨ Nuovo Boost!", color=PURPLE, timestamp=now())
            e.add_field(name="Utente", value=f"{after.mention} (`{after.id}`)", inline=False)
            e.add_field(name="Boost totali", value=str(guild.premium_subscription_count), inline=False)
            e.set_thumbnail(url=after.display_avatar.url)
            await self._send(guild, "actions", "boost", e)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.avatar == after.avatar:
            return
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if member:
                e = discord.Embed(title="🖼️ Foto profilo cambiata", color=ORANGE, timestamp=now())
                e.add_field(name="Utente", value=f"{after.mention} (`{after.id}`)", inline=False)
                e.set_thumbnail(url=after.display_avatar.url)
                await self._send(guild, "member", "avatar", e)

    # ── ROLE ──────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        e = discord.Embed(title="🎭 Ruolo creato", color=GREEN, timestamp=now())
        e.add_field(name="Ruolo", value=f"{role.mention} (`{role.id}`)", inline=False)
        await self._send(role.guild, "role", "create", e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        e = discord.Embed(title="🎭 Ruolo eliminato", color=RED, timestamp=now())
        e.add_field(name="Ruolo", value=f"{role.name} (`{role.id}`)", inline=False)
        await self._send(role.guild, "role", "delete", e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        modifiche = []
        if before.name != after.name:
            modifiche.append(f"**Nome:** {before.name} → {after.name}")
        if before.color != after.color:
            modifiche.append(f"**Colore:** {before.color} → {after.color}")
        if before.permissions != after.permissions:
            modifiche.append("**Permessi** modificati")
        if not modifiche:
            return
        e = discord.Embed(title="🎭 Ruolo modificato", color=ORANGE, timestamp=now(),
                          description="\n".join(modifiche))
        e.add_field(name="Ruolo", value=f"{after.mention} (`{after.id}`)", inline=False)
        await self._send(after.guild, "role", "update", e)

    # ── CHANNEL ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        e = discord.Embed(title="📁 Canale creato", color=GREEN, timestamp=now())
        e.add_field(name="Canale", value=f"{channel.mention} (`{channel.id}`)", inline=False)
        await self._send(channel.guild, "channel", "create", e)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        e = discord.Embed(title="📁 Canale eliminato", color=RED, timestamp=now())
        e.add_field(name="Canale", value=f"{channel.name} (`{channel.id}`)", inline=False)
        await self._send(channel.guild, "channel", "delete", e)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        modifiche = []
        if before.name != after.name:
            modifiche.append(f"**Nome:** {before.name} → {after.name}")
        if not modifiche:
            return
        e = discord.Embed(title="📁 Canale modificato", color=ORANGE, timestamp=now(),
                          description="\n".join(modifiche))
        e.add_field(name="Canale", value=f"{after.mention} (`{after.id}`)", inline=False)
        await self._send(after.guild, "channel", "update", e)

    # ── EMOJI ─────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        prima = {e.id for e in before}
        dopo = {e.id for e in after}
        aggiunte = [e for e in after if e.id not in prima]
        rimosse = [e for e in before if e.id not in dopo]

        for emo in aggiunte:
            e = discord.Embed(title="😀 Emoji creata", color=GREEN, timestamp=now())
            e.add_field(name="Emoji", value=f"{emo} `:{emo.name}:`", inline=False)
            await self._send(guild, "emoji", "create", e)
        for emo in rimosse:
            e = discord.Embed(title="😀 Emoji eliminata", color=RED, timestamp=now())
            e.add_field(name="Emoji", value=f"`:{emo.name}:`", inline=False)
            await self._send(guild, "emoji", "delete", e)
        # rinomini
        nomi_prima = {e.id: e.name for e in before}
        for emo in after:
            if emo.id in nomi_prima and nomi_prima[emo.id] != emo.name:
                e = discord.Embed(title="😀 Emoji rinominata", color=ORANGE, timestamp=now())
                e.add_field(name="Emoji", value=f"{emo} `:{nomi_prima[emo.id]}:` → `:{emo.name}:`", inline=False)
                await self._send(guild, "emoji", "update", e)

    # ── VOICE ─────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        lines = []
        color = BLUE

        if before.channel != after.channel:
            if before.channel is None:
                lines.append(f"➡️ è entrato in **{after.channel.name}**")
                color = GREEN
            elif after.channel is None:
                lines.append(f"⬅️ è uscito da **{before.channel.name}**")
                color = RED
            else:
                lines.append(f"🔀 spostato: **{before.channel.name}** → **{after.channel.name}**")

        if before.self_mute != after.self_mute:
            lines.append("🔇 si è mutato" if after.self_mute else "🎙️ si è smutato")
        if before.self_deaf != after.self_deaf:
            lines.append("🔈 si è sordinato" if after.self_deaf else "🔊 si è desordinato")
        if before.self_stream != after.self_stream:
            lines.append("🔴 ha iniziato lo streaming" if after.self_stream else "⚫ ha terminato lo streaming")
        if before.self_video != after.self_video:
            lines.append("📷 ha acceso la camera" if after.self_video else "📷 ha spento la camera")
        if before.mute != after.mute:
            lines.append("🔇 mutato dal server" if after.mute else "🔊 smutato dal server")
        if before.deaf != after.deaf:
            lines.append("🔈 sordinato dal server" if after.deaf else "🔊 desordinato dal server")

        if not lines:
            return
        e = discord.Embed(title="🔊 Attività vocale", description="\n".join(lines), color=color, timestamp=now())
        e.add_field(name="Membro", value=f"{member.mention} (`{member.id}`)", inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        await self._send(guild, "voice", "state", e)

    # ── SERVER ────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        modifiche = []
        if before.name != after.name:
            modifiche.append(f"**Nome:** {before.name} → {after.name}")
        if before.icon != after.icon:
            modifiche.append("**Icona** cambiata")
        if before.owner_id != after.owner_id:
            modifiche.append(f"**Proprietario:** <@{before.owner_id}> → <@{after.owner_id}>")
        if not modifiche:
            return
        e = discord.Embed(title="🛠️ Server modificato", color=ORANGE, timestamp=now(),
                          description="\n".join(modifiche))
        await self._send(after, "server", "update", e)

    # ── ACTIONS ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        e = discord.Embed(title="✉️ Invito creato", color=BLUE, timestamp=now())
        if invite.inviter:
            e.add_field(name="Creato da", value=invite.inviter.mention, inline=False)
        e.add_field(name="Codice", value=f"`{invite.code}`", inline=True)
        if invite.max_uses:
            e.add_field(name="Usi massimi", value=str(invite.max_uses), inline=True)
        await self._send(invite.guild, "actions", "invite", e)


async def setup(bot):
    await bot.add_cog(Logs(bot))
