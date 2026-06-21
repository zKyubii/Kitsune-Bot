import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

import database as db
import logconfig

ROMA = ZoneInfo("Europe/Rome")


def fmt(text, guild):
    return (text or "").replace("{server}", guild.name).replace("{membercount}", str(guild.member_count))


class AutoMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_sent = {}  # guild_id -> {msg_id: date}
        self.loop_msg.start()

    def cog_unload(self):
        self.loop_msg.cancel()

    @tasks.loop(minutes=1)
    async def loop_msg(self):
        adesso = datetime.datetime.now(ROMA)
        hhmm = adesso.strftime("%H:%M")
        oggi = adesso.date()
        for guild in list(self.bot.guilds):
            config = db.get_log_config(guild.id)
            if not logconfig.feature_enabled(config, "automsg"):
                continue
            am = config.get("automsg", {})
            ch = guild.get_channel(am.get("channel")) if am.get("channel") else None
            if not ch:
                continue
            sent = self.last_sent.setdefault(guild.id, {})
            for m in am.get("messages", []):
                mid = m.get("id")
                if m.get("time") == hhmm and sent.get(mid) != oggi:
                    sent[mid] = oggi
                    try:
                        await ch.send(fmt(m.get("message", ""), guild),
                                      allowed_mentions=discord.AllowedMentions(everyone=True, roles=True))
                    except discord.HTTPException:
                        pass

    @loop_msg.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AutoMessages(bot))
