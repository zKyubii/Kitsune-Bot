import discord
from discord.ext import commands
from discord import app_commands
import io
import asyncio
from PIL import Image, ImageDraw, ImageFont

import database as db
import logconfig
from cogs.fun import _segmenta, _render_emoji

W, H = 1000, 500
TRIGGER = ("+quote", "?quote")

# Font disponibili: chiave -> (nome mostrato, file normale, file bold)
FONTS = {
    "arial": ("Arial", "arial.ttf", "arialbd.ttf"),
    "segoe": ("Segoe UI", "segoeui.ttf", "segoeuib.ttf"),
    "comic": ("Comic Sans", "comic.ttf", "comicbd.ttf"),
    "times": ("Times New Roman", "times.ttf", "timesbd.ttf"),
    "georgia": ("Georgia", "georgia.ttf", "georgiab.ttf"),
    "verdana": ("Verdana", "verdana.ttf", "verdanab.ttf"),
    "trebuchet": ("Trebuchet MS", "trebuc.ttf", "trebucbd.ttf"),
    "impact": ("Impact", "impact.ttf", "impact.ttf"),
    "courier": ("Courier", "cour.ttf", "courbd.ttf"),
    "bahnschrift": ("Bahnschrift", "bahnschrift.ttf", "bahnschrift.ttf"),
}


# Fallback Linux quando il font specifico di Windows non c'è
_LINUX_FALLBACK = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_LINUX_FALLBACK_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _make_font(font_key: str, size: int, bold: bool):
    fam = FONTS.get(font_key, FONTS["arial"])
    file = fam[2] if bold else fam[1]
    candidati = [f"C:/Windows/Fonts/{file}", "C:/Windows/Fonts/arial.ttf"]
    candidati += _LINUX_FALLBACK_BOLD if bold else _LINUX_FALLBACK
    for path in candidati:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _emoji_h(font):
    return int(getattr(font, "size", 30) * 0.9)


def _measure(testo, font):
    target_h = _emoji_h(font)
    tot = 0
    for s, e in _segmenta(testo):
        if e:
            tot += target_h * max(1, len(s))
        else:
            tot += font.getlength(s)
    return tot


def _draw_centered(canvas, cx, cy, testo, font, fill):
    draw = ImageDraw.Draw(canvas)
    target_h = _emoji_h(font)
    parti, tot = [], 0
    for s, e in _segmenta(testo):
        if e:
            img = _render_emoji(s, target_h)
            if img:
                parti.append(("emoji", img, img.width))
                tot += img.width
        else:
            w = font.getlength(s)
            parti.append(("testo", s, w))
            tot += w
    x = cx - tot / 2
    for tipo, cont, w in parti:
        if tipo == "emoji":
            canvas.alpha_composite(cont, (int(x), int(cy - cont.height / 2)))
        else:
            draw.text((x, cy), cont, font=font, anchor="lm", fill=fill)
        x += w


def _wrap(testo, font, max_w):
    parole = testo.split()
    righe, cur = [], ""
    for p in parole:
        prova = (cur + " " + p).strip()
        if _measure(prova, font) <= max_w or not cur:
            cur = prova
        else:
            righe.append(cur)
            cur = p
    if cur:
        righe.append(cur)
    return righe


def genera_quote(av_bytes: bytes, testo: str, nome: str, handle: str, opts: dict) -> io.BytesIO:
    font_key = opts.get("font", "arial")
    bold = opts.get("bold", False)
    bgmode = opts.get("bg", "black")
    side = opts.get("side", "left")

    bg = (0, 0, 0) if bgmode == "black" else (245, 245, 245)
    fg = (245, 245, 245) if bgmode == "black" else (15, 15, 15)
    sub = (140, 140, 140)
    wm_col = (95, 95, 100) if bgmode == "black" else (160, 160, 160)

    canvas = Image.new("RGBA", (W, H), bg + (255,))

    # Avatar in scala di grigi
    av = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
    lato = min(av.size)
    av = av.crop(((av.width - lato) // 2, (av.height - lato) // 2,
                  (av.width - lato) // 2 + lato, (av.height - lato) // 2 + lato))
    av = av.resize((H, H)).convert("L").convert("RGBA")

    # Sfumatura verso lo sfondo
    grad = Image.new("RGBA", (H, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(H):
        t = (x - H * 0.35) / (H * 0.65)
        a = int(max(0.0, min(1.0, t)) * 255)
        gd.line([(x, 0), (x, H)], fill=bg + (a,))

    if side == "left":
        canvas.paste(av, (0, 0))
        canvas.alpha_composite(grad, (0, 0))
        tx0, tx1 = 530, 965
    else:
        canvas.paste(av, (W - H, 0))
        canvas.alpha_composite(grad.transpose(Image.FLIP_LEFT_RIGHT), (W - H, 0))
        tx0, tx1 = 35, 470

    max_w = tx1 - tx0
    cx = (tx0 + tx1) // 2

    if len(testo) > 300:
        testo = testo[:297] + "..."

    # Font adattivo
    size = 58
    while size > 22:
        font = _make_font(font_key, size, bold)
        righe = _wrap(testo, font, max_w)
        line_h = int(size * 1.25)
        totale = len(righe) * line_h
        if totale <= 300 and all(_measure(r, font) <= max_w for r in righe):
            break
        size -= 2

    y = int(H * 0.40) - totale // 2
    for r in righe:
        _draw_centered(canvas, cx, y + line_h // 2, r, font, fg)
        y += line_h

    y += 18
    _draw_centered(canvas, cx, y, f"- {nome}", _make_font(font_key, 30, bold), fg)
    y += 34
    _draw_centered(canvas, cx, y, handle, _make_font(font_key, 20, False), sub)

    draw = ImageDraw.Draw(canvas)
    draw.text((W - 14, H - 14), "Kitsune • Quote", fill=wm_col, anchor="rs",
              font=_make_font("arial", 15, False))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


def _destinazione(guild: discord.Guild, fallback):
    """Canale dove pubblicare la quote: quello impostato in dashboard, o quello del comando."""
    config = db.get_log_config(guild.id)
    cid = config.get("quote_channel")
    if cid:
        ch = guild.get_channel(cid)
        if ch:
            return ch
    return fallback


# ── PANNELLO DI PERSONALIZZAZIONE ───────────────────────────────────────────
class FontSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=fam[0], value=k, default=(k == "arial"))
            for k, fam in FONTS.items()
        ]
        super().__init__(placeholder="🎨 Seleziona Font", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.opts["font"] = self.values[0]
        for o in self.options:
            o.default = (o.value == self.values[0])
        await self.view.regen(interaction)


class SfondoButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Sfondo", emoji="🎨", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        v.opts["bg"] = "white" if v.opts["bg"] == "black" else "black"
        await v.regen(interaction)


class PosizioneButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Posizione", emoji="↔️", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        v.opts["side"] = "right" if v.opts["side"] == "left" else "left"
        await v.regen(interaction)


class GrassettoButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Grassetto", emoji="🔠", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        v.opts["bold"] = not v.opts["bold"]
        self.style = discord.ButtonStyle.success if v.opts["bold"] else discord.ButtonStyle.secondary
        await v.regen(interaction)


class RimuoviButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Rimuovi questa quote", emoji="🗑️", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🗑️ Quote rimossa.", ephemeral=True)
        try:
            await interaction.message.delete()
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass


class QuoteView(discord.ui.View):
    def __init__(self, av_bytes, testo, nome, handle, autore_id):
        super().__init__(timeout=300)
        self.av = av_bytes
        self.testo = testo
        self.nome = nome
        self.handle = handle
        self.autore_id = autore_id
        self.opts = {"font": "arial", "bold": False, "bg": "black", "side": "left"}
        self.message = None
        self.add_item(FontSelect())
        self.add_item(SfondoButton())
        self.add_item(PosizioneButton())
        self.add_item(GrassettoButton())
        self.add_item(RimuoviButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message(
                "❌ Solo chi ha creato la quote può modificarla.", ephemeral=True
            )
            return False
        return True

    async def regen(self, interaction: discord.Interaction):
        buf = await asyncio.to_thread(
            genera_quote, self.av, self.testo, self.nome, self.handle, self.opts
        )
        file = discord.File(buf, filename="quote.png")
        await interaction.response.edit_message(attachments=[file], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.HTTPException, discord.NotFound):
                pass


# ── COG ─────────────────────────────────────────────────────────────────────
class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name="Make it a Quote", callback=self.make_quote)
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def _pubblica(self, guild, fallback_channel, src_message, autore_id):
        dest = _destinazione(guild, fallback_channel)
        autore = src_message.author
        av = await autore.display_avatar.replace(size=512).read()
        view = QuoteView(av, src_message.content, autore.display_name, f"@{autore.name}", autore_id)
        buf = await asyncio.to_thread(genera_quote, av, src_message.content, view.nome, view.handle, view.opts)
        msg = await dest.send(file=discord.File(buf, filename="quote.png"), view=view)
        view.message = msg
        return dest

    # Tasto destro → App → Make it a Quote
    async def make_quote(self, interaction: discord.Interaction, message: discord.Message):
        config = db.get_log_config(interaction.guild_id)
        if not logconfig.feature_enabled(config, "quote"):
            await interaction.response.send_message(
                "🚫 La funzione Quote è disattivata su questo server.", ephemeral=True)
            return
        if not message.content:
            await interaction.response.send_message(
                "❌ Questo messaggio non ha testo da citare.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        dest = await self._pubblica(interaction.guild, interaction.channel, message, interaction.user.id)
        await interaction.followup.send(
            f"✅ Quote creata in {dest.mention}! Personalizzala con i bottoni sul messaggio.",
            ephemeral=True,
        )

    # Rispondi con "?quote"
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.strip().lower() not in TRIGGER or not message.reference:
            return

        config = db.get_log_config(message.guild.id)
        if not logconfig.feature_enabled(config, "quote"):
            return

        ref = message.reference.resolved
        if ref is None or isinstance(ref, discord.DeletedReferencedMessage):
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
            except (discord.NotFound, discord.HTTPException):
                return
        if not ref.content:
            await message.channel.send("❌ Quel messaggio non ha testo da citare.", delete_after=5)
            return

        await self._pubblica(message.guild, message.channel, ref, message.author.id)
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(Quote(bot))
