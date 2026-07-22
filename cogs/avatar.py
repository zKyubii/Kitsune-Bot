import discord
from discord.ext import commands

from cogs.profile import privacy_blocked, privacy_notify

BLU = 0x5865F2


async def _privacy_stop(ctx, target, kind: str) -> bool:
    """True (e avvisa) se 'target' ha bloccato avatar/banner a chi esegue il comando."""
    if not privacy_blocked(ctx.guild, ctx.author, target, kind):
        return False
    if privacy_notify(target):
        etichetta = "l'avatar" if kind == "avatar" else "il banner"
        await ctx.send(f"🔒 {target.display_name} ha la privacy attiva su {etichetta}.")
    return True


def _url(asset: discord.Asset) -> str:
    """URL dell'asset a 1024px, in GIF se è animato (così pfp/banner animati si vedono animati)."""
    if asset.is_animated():
        return asset.replace(format="gif", size=1024).url
    return asset.replace(size=1024).url


class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _embed(self, target: discord.abc.User, titolo: str, asset: discord.Asset) -> discord.Embed:
        colore = target.color if getattr(target, "color", None) and target.color.value else BLU
        embed = discord.Embed(title=titolo, color=colore)
        embed.set_author(name=str(target), icon_url=target.display_avatar.url)
        embed.set_image(url=_url(asset))
        return embed

    # ── AVATAR ───────────────────────────────────────────────────────────────
    @commands.command(name="av")
    @commands.guild_only()
    async def av(self, ctx: commands.Context, target: discord.Member = None):
        """Avatar del SERVER (quello che hai nel server)."""
        target = target or ctx.author
        if await _privacy_stop(ctx, target, "avatar"):
            return
        await ctx.send(embed=self._embed(target, "Server Avatar", target.display_avatar))

    @commands.command(name="avuser")
    @commands.guild_only()
    async def avuser(self, ctx: commands.Context, target: discord.Member = None):
        """Avatar del PROFILO (globale)."""
        target = target or ctx.author
        if await _privacy_stop(ctx, target, "avatar"):
            return
        glob = target.avatar or target.default_avatar
        await ctx.send(embed=self._embed(target, "Avatar", glob))

    # ── BANNER ───────────────────────────────────────────────────────────────
    @commands.command(name="banner")
    @commands.guild_only()
    async def banner(self, ctx: commands.Context, target: discord.Member = None):
        """Banner del SERVER (se impostato), altrimenti quello del profilo."""
        target = target or ctx.author
        if await _privacy_stop(ctx, target, "banner"):
            return
        asset = target.guild_banner
        titolo = "Server Banner"
        if asset is None:
            user = await self.bot.fetch_user(target.id)   # il banner globale va recuperato
            asset = user.banner
            titolo = "Banner"
        if asset is None:
            await ctx.send(_t(ctx, "avatar.no_banner", user=target.display_name))
            return
        await ctx.send(embed=self._embed(target, titolo, asset))

    @commands.command(name="banneruser")
    @commands.guild_only()
    async def banneruser(self, ctx: commands.Context, target: discord.Member = None):
        """Banner del PROFILO (globale)."""
        target = target or ctx.author
        if await _privacy_stop(ctx, target, "banner"):
            return
        user = await self.bot.fetch_user(target.id)
        if user.banner is None:
            await ctx.send(_t(ctx, "avatar.no_profile_banner", user=target.display_name))
            return
        await ctx.send(embed=self._embed(user, "Banner", user.banner))


async def setup(bot):
    await bot.add_cog(Avatar(bot))
