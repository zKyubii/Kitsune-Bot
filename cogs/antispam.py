import discord
from discord.ext import commands
import time
import datetime
import collections

import database as db
import logconfig
from locales import t

# Finestre temporali (secondi)
WINDOW = 8            # finestra per il conteggio messaggi
COOLDOWN = 12         # non ripunire lo stesso utente entro X secondi

# Soglie di rilevamento
T_IMPORTANT = 12      # messaggi nella finestra = spam grave
T_SPAM = 7            # messaggi nella finestra = spam normale
T_MENTION_MSG = 6     # menzioni in un singolo messaggio
T_MENTION_TOT = 10    # menzioni totali nella finestra
T_LINKS = 5           # messaggi con link nella finestra
T_DUP = 4             # messaggi identici nella finestra
T_SELFBOT_CHANS = 3   # stesso messaggio in N canali diversi

PREFIXES = "!?./$-+;>"

# Pattern/testi tipici delle truffe (anti-scam sui link/testi)
SCAM = [
    "free nitro", "freenitro", "free-nitro", "nitro free", "gift nitro", "nitro gift",
    "discord-nitro", "discordnitro", "discordgift", "discord-gift", "dlscord", "discrod",
    "steamcommunity.com/gift", "@everyone free", "claim your", "airdrop", "free robux",
]


class Antispam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.history = collections.defaultdict(lambda: collections.deque(maxlen=40))
        self.cooldown = {}

    # ── UTILITY ─────────────────────────────────────────────────────────────
    async def _log(self, guild, embed):
        config = db.get_log_config(guild.id)
        cid = config.get("antispam", {}).get("log_channel")
        if cid:
            ch = guild.get_channel(cid)
            if ch:
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

    def _whitelisted(self, config, message):
        wl = config.get("antispam", {}).get("whitelist", {})
        if message.channel.id in wl.get("channels", []):
            return True
        if message.author.id in wl.get("users", []):
            return True
        if {r.id for r in message.author.roles} & set(wl.get("roles", [])):
            return True
        return False

    async def _sanziona(self, guild, member, sanction, seconds, motivo):
        try:
            if sanction == "warn":
                db.add_warning(guild.id, member.id, guild.me.id, motivo, None)
            elif sanction == "timeout":
                await member.timeout(datetime.timedelta(seconds=seconds or 600), reason=motivo)
            elif sanction == "kick":
                await member.kick(reason=motivo)
            elif sanction == "softban":
                await member.ban(reason=motivo, delete_message_days=1)
                await guild.unban(member, reason="Soft ban")
            elif sanction == "ban":
                await member.ban(reason=motivo, delete_message_days=1)
        except discord.HTTPException:
            return False
        return True

    async def _cancella(self, messaggi):
        for m in set(messaggi):
            try:
                await m.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    # ── ANTISPAM ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = db.get_log_config(message.guild.id)
        if not logconfig.antispam_attivo(config):
            return

        # I membri dello staff sono esentati
        perms = message.author.guild_permissions
        if perms.administrator or perms.manage_messages:
            return
        if self._whitelisted(config, message):
            return

        # ── Anti-scam ──
        if config.get("antispam", {}).get("antiscam"):
            low = message.content.lower()
            if any(s in low for s in SCAM):
                await self._cancella([message])
                cat = logconfig.categoria_cfg(config, "links")
                sanction = cat["sanction"] if cat["sanction"] != "none" else "ban"
                ok = await self._sanziona(message.guild, message.author, sanction, cat["seconds"],
                                          "Antispam: link/truffa rilevato")
                await self._segnala(message, "🎣 Scam rilevato", sanction if ok else "nessuna (errore)")
                return

        key = (message.guild.id, message.author.id)
        now = time.time()
        if now - self.cooldown.get(key, 0) < COOLDOWN:
            return

        record = {
            "t": now,
            "content": message.content.strip(),
            "channel": message.channel.id,
            "mentions": len(message.mentions) + len(message.role_mentions),
            "link": "http://" in message.content or "https://" in message.content,
            "embed": bool(message.embeds),
            "msg": message,
        }

        categoria = self._rileva(key, record)
        if not categoria:
            return

        cat = logconfig.categoria_cfg(config, categoria)
        if not cat["enabled"]:
            return

        # Punisci
        self.cooldown[key] = now
        recenti = list(self.history[key])
        self.history[key].clear()
        await self._cancella([r["msg"] for r in recenti])

        sanction = cat["sanction"]
        ok = True
        if sanction != "none":
            ok = await self._sanziona(message.guild, message.author, sanction, cat["seconds"],
                                      "Antispam: " + t(config, logconfig.SPAM_CATEGORIES[categoria]))

        await self._segnala(message, "🚨 " + t(config, logconfig.SPAM_CATEGORIES[categoria]),
                            sanction if ok else "nessuna (errore)", cat.get("seconds", 0))

    def _rileva(self, key, record):
        dq = self.history[key]
        dq.append(record)
        now = record["t"]
        while dq and now - dq[0]["t"] > WINDOW:
            dq.popleft()
        recenti = list(dq)
        n = len(recenti)

        if n >= T_IMPORTANT:
            return "important"
        if record["mentions"] >= T_MENTION_MSG or sum(r["mentions"] for r in recenti) >= T_MENTION_TOT:
            return "mentions"
        if sum(1 for r in recenti if r["link"]) >= T_LINKS:
            return "links"
        if record["content"] and sum(1 for r in recenti if r["content"] == record["content"]) >= T_DUP:
            return "duplicates"
        if record["embed"]:
            return "selfbot"
        if record["content"]:
            canali = {r["channel"] for r in recenti if r["content"] == record["content"]}
            if len(canali) >= T_SELFBOT_CHANS:
                return "selfbot"
        if record["content"][:1] in PREFIXES and sum(1 for r in recenti if r["content"][:1] in PREFIXES) >= 6:
            return "external"
        if n >= T_SPAM:
            return "spam"
        return None

    async def _segnala(self, message, titolo, sanzione, seconds=0):
        embed = discord.Embed(title=titolo, color=0xE74C3C,
                              timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="Utente", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Canale", value=message.channel.mention, inline=True)
        sanz = t(config, logconfig.SANCTIONS.get(sanzione, sanzione))
        if sanzione == "timeout" and seconds:
            sanz += f" ({seconds // 60} min)" if seconds >= 60 else f" ({seconds}s)"
        embed.add_field(name="Sanzione", value=sanz, inline=True)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        await self._log(message.guild, embed)


async def setup(bot):
    await bot.add_cog(Antispam(bot))
