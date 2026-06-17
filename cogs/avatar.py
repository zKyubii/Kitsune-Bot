import discord
from discord.ext import commands

BLU = 0x5865F2


class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _embed(self, target: discord.Member, titolo: str, asset: discord.Asset) -> discord.Embed:
        colore = target.color if getattr(target, "color", None) and target.color.value else BLU
        embed = discord.Embed(title=titolo, color=colore)
        embed.set_author(name=str(target), icon_url=target.display_avatar.url)
        embed.set_image(url=asset.replace(size=1024).url)
        return embed

    # +av [utente] → avatar del SERVER (quello che hai nel server)
    @commands.command(name="av")
    @commands.guild_only()
    async def av(self, ctx: commands.Context, target: discord.Member = None):
        target = target or ctx.author
        await ctx.send(embed=self._embed(target, "Server Avatar", target.display_avatar))

    # +avuser [utente] → avatar del PROFILO (globale)
    @commands.command(name="avuser")
    @commands.guild_only()
    async def avuser(self, ctx: commands.Context, target: discord.Member = None):
        target = target or ctx.author
        glob = target.avatar or target.default_avatar   # globale, ignora quello del server
        await ctx.send(embed=self._embed(target, "Avatar", glob))


async def setup(bot):
    await bot.add_cog(Avatar(bot))
