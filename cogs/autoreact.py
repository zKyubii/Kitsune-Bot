import re

import discord
from discord.ext import commands

import database as db
import logconfig

_MENTION_RE = re.compile(r"<@!?(\d+)>")


class AutoReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        config = db.get_log_config(message.guild.id)
        if not logconfig.feature_enabled(config, "autoreact"):
            return
        ar = config.get("autoreact", {})
        rules = ar.get("rules", [])
        if not rules:
            return
        bl = ar.get("blacklist_channels", [])
        if message.channel.id in bl or getattr(message.channel, "category_id", None) in bl:
            return

        content = (message.content or "").lower().strip()
        # solo i tag scritti davvero nel testo (esclude il "ping" automatico
        # che Discord aggiunge quando si risponde a un messaggio)
        mentioned = {int(uid) for uid in _MENTION_RE.findall(message.content or "")}
        for rule in rules:
            if not self._match(rule, content, mentioned):
                continue
            for raw in rule.get("emojis", [])[:5]:
                emo = self._emoji(raw)
                if emo is None:
                    continue
                try:
                    await message.add_reaction(emo)
                except discord.HTTPException:
                    pass

    @staticmethod
    def _match(rule, content, mentioned) -> bool:
        if rule.get("type") == "mention":
            try:
                uid = int(rule["trigger"])
            except (ValueError, KeyError, TypeError):
                return False
            if uid not in mentioned:
                return False
            if rule.get("mode") == "exact":
                # "solo il tag": il messaggio è SOLO la menzione
                return content in (f"<@{uid}>", f"<@!{uid}>")
            return True
        trig = str(rule.get("trigger", "")).lower().strip()
        if not trig:
            return False
        if rule.get("mode") == "exact":
            return content == trig
        return trig in content

    @staticmethod
    def _emoji(raw):
        try:
            return discord.PartialEmoji.from_str(str(raw).strip())
        except Exception:
            return None


async def setup(bot):
    await bot.add_cog(AutoReact(bot))
