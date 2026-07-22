import time

import discord
from discord.ext import commands, tasks
from discord import app_commands

import database as db
from locales import t


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    """Scorciatoia: risolve la lingua del server da ctx o interaction."""
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)

import levelsystem as ls

BLU = 0x5865F2
DEAF_GRACE = 600  # secondi di tolleranza in cuffia (full mute) prima di smettere di dare XP


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.text_cd = {}    # (guild_id, user_id) -> last unix ts (chat)
        self.voice_cd = {}   # (guild_id, user_id) -> last unix ts (vocale)
        self.deaf_since = {}  # (guild_id, user_id) -> unix ts da quando è "full mute" (deafened)
        self.voice_loop.start()

    def cog_unload(self):
        self.voice_loop.cancel()

    # ── CORE XP ──────────────────────────────────────────────────────────────
    async def _award(self, member, base_amount, channel, c):
        mult = ls.get_multiplier(c, [r.id for r in member.roles])
        amount = int(base_amount * mult)
        if amount <= 0:
            return
        old_xp = db.get_xp(member.guild.id, member.id)
        old_level = ls.level_from_xp(c, old_xp)
        new_xp = db.add_xp(member.guild.id, member.id, amount)
        new_level = ls.level_from_xp(c, new_xp)
        if new_level > old_level:
            await self._sync_rewards(member, c, new_level)
            await self._levelup_message(member, c, new_level, channel)
        elif new_level < old_level:
            await self._sync_rewards(member, c, new_level)

    async def _levelup_message(self, member, c, level, fallback_channel):
        if level <= 0:
            return
        ch = member.guild.get_channel(c.get("levelup_channel")) if c.get("levelup_channel") else fallback_channel
        if not ch:
            return

        def fmt(t):
            return (t or "").replace("{user}", member.mention).replace("{user_name}", member.name) \
                .replace("{level}", str(level)).replace("{server}", member.guild.name)

        titolo = fmt(c.get("levelup_title"))
        corpo = fmt(c.get("levelup_message"))
        colore = member.color if member.color.value else discord.Color(0xF1C40F)
        custom = (c.get("levelup_color") or "").strip().lstrip("#")
        if custom:
            try:
                colore = discord.Color(int(custom, 16))
            except ValueError:
                pass
        embed = discord.Embed(title=titolo or None, description=corpo or None, color=colore)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=member.guild.name,
                         icon_url=member.guild.icon.url if member.guild.icon else None)
        try:
            await ch.send(content=member.mention, embed=embed,
                          allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            pass

    async def _sync_rewards(self, member, c, level):
        """Allinea i ruoli-premio del membro al suo livello (replace o accumulo)."""
        rewards = c.get("rewards", {})
        if not rewards:
            return
        all_ids = {int(rid) for rid in rewards.values()}
        earned = sorted((int(lv), int(rid)) for lv, rid in rewards.items() if int(lv) <= level)
        if c.get("reward_replace", True):
            target = {earned[-1][1]} if earned else set()
        else:
            target = {rid for _, rid in earned}

        me = member.guild.me
        to_add, to_remove = [], []
        for rid in all_ids:
            role = member.guild.get_role(rid)
            if not role or role.managed or role >= me.top_role:
                continue
            has = role in member.roles
            if rid in target and not has:
                to_add.append(role)
            elif rid not in target and has:
                to_remove.append(role)
        try:
            if to_add:
                await member.add_roles(*to_add, reason="Ricompensa livello")
            if to_remove:
                await member.remove_roles(*to_remove, reason="Ricompensa livello")
        except discord.HTTPException:
            pass

    # ── MESSAGGI ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        c = ls.cfg(db.get_log_config(message.guild.id))
        if not c["enabled"] or not c["text_enabled"]:
            return
        member = message.author
        if ls.is_blacklisted(c, member.id, [r.id for r in member.roles]):
            return
        if ls.channel_blacklisted(c, message.channel.id, getattr(message.channel, "category_id", None)):
            return
        key = (message.guild.id, member.id)
        now = time.time()
        if now - self.text_cd.get(key, 0) < c["cooldown_text"]:
            return
        self.text_cd[key] = now
        await self._award(member, int(c["xp_message"]), message.channel, c)

    # ── VOCALE ───────────────────────────────────────────────────────────────
    @tasks.loop(seconds=30)
    async def voice_loop(self):
        now = time.time()
        for guild in list(self.bot.guilds):
            c = ls.cfg(db.get_log_config(guild.id))
            if not c["enabled"] or not c["voice_enabled"]:
                continue
            for vc in guild.voice_channels:
                if guild.afk_channel and vc.id == guild.afk_channel.id:
                    continue
                if ls.channel_blacklisted(c, vc.id, vc.category_id):
                    continue
                humans = [m for m in vc.members if not m.bot]
                if len(humans) < 2:   # niente XP se sei da solo
                    continue
                # Serve almeno una persona col MIC ATTIVO: se sono tutti mic-mutati
                # (o server-mutati) il canale è "morto" → niente XP a nessuno.
                if not any(m.voice and not (m.voice.self_mute or m.voice.mute) for m in humans):
                    continue
                for member in humans:
                    vs = member.voice
                    if not vs or vs.afk:
                        continue
                    key = (guild.id, member.id)
                    # Full mute (in cuffia / deafened): tolleranza, poi stop XP dopo DEAF_GRACE.
                    # Il solo mic mutato NON conta come full mute: continua a dare XP.
                    if vs.self_deaf or vs.deaf:
                        since = self.deaf_since.get(key)
                        if since is None:
                            self.deaf_since[key] = now
                        elif now - since >= DEAF_GRACE:
                            continue
                    else:
                        self.deaf_since.pop(key, None)
                    if ls.is_blacklisted(c, member.id, [r.id for r in member.roles]):
                        continue
                    if now - self.voice_cd.get(key, 0) < c["cooldown_voice"]:
                        continue
                    self.voice_cd[key] = now
                    await self._award(member, int(c["voice_xp"]), vc, c)

    @voice_loop.before_loop
    async def _before_voice(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Quando l'utente esce o cambia canale, azzera il timer della cuffia
        # (altrimenti uno stato vecchio lo bloccherebbe al rientro).
        if before.channel != after.channel:
            self.deaf_since.pop((member.guild.id, member.id), None)

    # ── COLEAVE ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        c = ls.cfg(db.get_log_config(member.guild.id))
        if c["enabled"] and c["coleave"]:
            db.reset_level_user(member.guild.id, member.id)

    # ── UTILITY ──────────────────────────────────────────────────────────────
    @staticmethod
    def _bar(into, need, length=14):
        need = max(1, need)
        filled = int(length * min(into, need) / need)
        return "▰" * filled + "▱" * (length - filled)

    # ── +rank / +r ───────────────────────────────────────────────────────────
    @commands.command(name="rank", aliases=["r"])
    @commands.guild_only()
    async def rank(self, ctx: commands.Context, utente: discord.Member = None):
        c = ls.cfg(db.get_log_config(ctx.guild.id))
        if not c["enabled"]:
            await ctx.send(_t(ctx, "lvl.disabled"))
            return
        member = utente or ctx.author
        xp = db.get_xp(ctx.guild.id, member.id)
        info = ls.level_info(c, xp)
        rank = f"#{db.level_rank(ctx.guild.id, member.id)}" if xp > 0 else "—"

        embed = discord.Embed(color=member.color if member.color.value else BLU)
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.description = self._bar(info["into"], info["need"])
        embed.add_field(name="Livello", value=f"**{info['level']}**", inline=True)
        embed.add_field(name="Rank server", value=f"**{rank}**", inline=True)
        embed.add_field(name="Exp", value=f"**{xp}** / {info['next_total']}", inline=True)
        await ctx.send(embed=embed)

    # ── +leaderboard ──────────────────────────────────────────────────────────
    @commands.command(name="leaderboard", aliases=["lb"])
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        c = ls.cfg(db.get_log_config(ctx.guild.id))
        rows = db.level_top(ctx.guild.id, 10)
        if not rows:
            await ctx.send(_t(ctx, "lvl.no_xp"))
            return
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        lines = []
        for i, r in enumerate(rows):
            info = ls.level_info(c, r["xp"])
            pos = medals.get(i, f"`#{i + 1}`")
            lines.append(f"{pos} <@{r['user_id']}>\n　**Level:** `{info['level']}`　**Exp:** `{r['xp']}/{info['next_total']}`")
        embed = discord.Embed(title=_t(ctx, "lvl.leaderboard_title", guild=ctx.guild.name),
                              color=BLU, description="\n\n".join(lines))
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)

    # ── /level (admin) ───────────────────────────────────────────────────────
    level_group = app_commands.Group(
        name="level", description="Gestione XP livelli (admin)",
        default_permissions=discord.Permissions(administrator=True), guild_only=True)

    async def _post_change(self, guild_id, member):
        c = ls.cfg(db.get_log_config(guild_id))
        await self._sync_rewards(member, c, ls.level_from_xp(c, db.get_xp(guild_id, member.id)))

    @level_group.command(name="give", description="Dà XP a un utente")
    @app_commands.checks.has_permissions(administrator=True)
    async def give(self, interaction: discord.Interaction, utente: discord.Member, quantita: int):
        new = db.add_xp(interaction.guild_id, utente.id, quantita)
        await self._post_change(interaction.guild_id, utente)
        c = ls.cfg(db.get_log_config(interaction.guild_id))
        await interaction.response.send_message(
            _t(interaction, "lvl.xp_given",
               verb=_t(interaction, "lvl.verb_given" if quantita >= 0 else "lvl.verb_taken"),
               amount=abs(quantita), user=utente.mention)
            + " "
            + _t(interaction, "lvl.xp_now", xp=new, level=ls.level_from_xp(c, new)),
            ephemeral=True)

    @level_group.command(name="giverole", description="Dà XP a tutti i membri con un ruolo")
    @app_commands.checks.has_permissions(administrator=True)
    async def giverole(self, interaction: discord.Interaction, ruolo: discord.Role, quantita: int):
        await interaction.response.defer(ephemeral=True)
        n = 0
        for m in ruolo.members:
            if m.bot:
                continue
            db.add_xp(interaction.guild_id, m.id, quantita)
            await self._post_change(interaction.guild_id, m)
            n += 1
        await interaction.followup.send(
            _t(interaction, "lvl.xp_given_role", verb=_t(interaction, "lvl.verb_given" if quantita >= 0 else "lvl.verb_taken"), amount=abs(quantita), count=n, role=ruolo.mention),
            ephemeral=True)

    @level_group.command(name="set", description="Imposta gli XP totali di un utente")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_cmd(self, interaction: discord.Interaction, utente: discord.Member, xp: int):
        db.set_xp(interaction.guild_id, utente.id, xp)
        await self._post_change(interaction.guild_id, utente)
        c = ls.cfg(db.get_log_config(interaction.guild_id))
        await interaction.response.send_message(
            _t(interaction, "lvl.xp_set", user=utente.mention, xp=max(0, xp), level=ls.level_from_xp(c, max(0, xp))),
            ephemeral=True)

    @level_group.command(name="reset", description="Azzera gli XP di un utente")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, utente: discord.Member):
        db.reset_level_user(interaction.guild_id, utente.id)
        await self._post_change(interaction.guild_id, utente)
        await interaction.response.send_message(_t(interaction, "lvl.xp_reset", user=utente.mention), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Levels(bot))
