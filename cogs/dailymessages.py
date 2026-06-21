import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

import database as db
import logconfig

ROMA = ZoneInfo("Europe/Rome")

DEFAULT_MORNING_TIME = "08:00"
DEFAULT_NIGHT_TIME = "00:00"
DEFAULT_MORNING = "☀️ **Buongiorno {server}!** Passate una splendida giornata 💛"
DEFAULT_NIGHT = "🌙 **Buonanotte a tutti!** Sogni d'oro 💤"


def fmt(text, guild):
    return (text or "").replace("{server}", guild.name).replace("{membercount}", str(guild.member_count))


class DailyMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_sent = {}  # guild_id -> {"morning": date, "night": date}
        self.daily_loop.start()

    def cog_unload(self):
        self.daily_loop.cancel()

    @tasks.loop(minutes=1)
    async def daily_loop(self):
        adesso = datetime.datetime.now(ROMA)
        hhmm = adesso.strftime("%H:%M")
        oggi = adesso.date()
        for guild in list(self.bot.guilds):
            config = db.get_log_config(guild.id)
            if not logconfig.feature_enabled(config, "daily"):
                continue
            d = config.get("daily", {})
            ch = guild.get_channel(d.get("channel")) if d.get("channel") else None
            if not ch:
                continue
            sent = self.last_sent.setdefault(guild.id, {})
            if hhmm == d.get("morning_time", DEFAULT_MORNING_TIME) and sent.get("morning") != oggi:
                sent["morning"] = oggi
                await self._invia(ch, d.get("morning_msg") or DEFAULT_MORNING, guild)
            if hhmm == d.get("night_time", DEFAULT_NIGHT_TIME) and sent.get("night") != oggi:
                sent["night"] = oggi
                await self._invia(ch, d.get("night_msg") or DEFAULT_NIGHT, guild)

    async def _invia(self, channel, testo, guild):
        try:
            await channel.send(fmt(testo, guild),
                               allowed_mentions=discord.AllowedMentions(everyone=True, roles=True))
        except discord.HTTPException:
            pass

    @daily_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(DailyMessages(bot))
