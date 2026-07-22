import discord
from discord.ext import commands
import random
import asyncio
import io
import os
import math
import datetime
import unicodedata
import aiohttp
from PIL import Image, ImageDraw, ImageFont

import database as db
from locales import t, tlist


def _t(ctx_or_inter, key: str, **kwargs) -> str:
    gid = getattr(ctx_or_inter, "guild_id", None) or ctx_or_inter.guild.id
    return t(db.get_log_config(gid), key, **kwargs)

import logconfig

ROSA = (255, 140, 200)
W, H = 800, 450

# Se metti un'immagine qui, verrà usata come sfondo al posto di quello generato
SFONDO_PERSONALIZZATO = os.path.join(os.path.dirname(__file__), "..", "assets", "ship_bg.png")

# Cache su disco delle emoji Twemoji (stesse di Discord)
_EMOJI_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "emoji_cache")


# Percorsi font candidati (Windows + Linux) — usa il primo disponibile
_FONT_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_NORMAL = [
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT_EMOJI = [
    "C:/Windows/Fonts/seguiemj.ttf",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
]


def _carica(percorsi, size):
    for p in percorsi:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return None


def _font(size: int, bold: bool = True):
    f = _carica(_FONT_BOLD if bold else _FONT_NORMAL, size)
    return f if f else ImageFont.load_default()


_EMOJI_FONT_CACHE = "__non_caricato__"


def _emoji_font():
    """Font emoji a dimensione 'nativa' per il rendering (poi scaliamo l'immagine)."""
    global _EMOJI_FONT_CACHE
    if _EMOJI_FONT_CACHE != "__non_caricato__":
        return _EMOJI_FONT_CACHE
    for p in _FONT_EMOJI:
        for sz in (137, 136, 128, 109, 96, 64, 48, 32):
            try:
                _EMOJI_FONT_CACHE = ImageFont.truetype(p, sz)
                return _EMOJI_FONT_CACHE
            except Exception:
                continue
    _EMOJI_FONT_CACHE = None
    return None


def _render_emoji(testo: str, target_h: int):
    """Disegna le emoji e le ridimensiona all'altezza voluta (fix emoji giganti su Linux)."""
    ef = _emoji_font()
    if ef is None:
        return None
    larghezza = 170 * max(1, len(testo)) + 60
    tmp = Image.new("RGBA", (larghezza, 240), (0, 0, 0, 0))
    try:
        ImageDraw.Draw(tmp).text((10, 10), testo, font=ef, embedded_color=True)
    except Exception:
        return None
    bbox = tmp.getbbox()
    if not bbox:
        return None
    em = tmp.crop(bbox)
    scala = target_h / em.height
    return em.resize((max(1, int(em.width * scala)), target_h), Image.LANCZOS)


def _normalizza_nome(testo: str) -> str:
    """Converte i font 'fancy' unicode (fraktur/grassetto/corsivo, es. 𝕸𝖔𝖓𝖘𝖙𝖊𝖗 → Monster)
    in lettere normali, così il font li disegna invece di mostrare □. Le emoji restano."""
    testo = unicodedata.normalize("NFKC", testo)
    testo = "".join(ch for ch in testo if unicodedata.category(ch) != "Cc")
    return testo.strip() or "?"


def _wrap_nome(testo: str, max_chars: int = 18, max_lines: int = 2):
    """Spezza il nome su più righe (max 2) senza tagliare le parole se possibile.
    Tronca con … solo se eccede davvero il limite."""
    testo = testo.strip() or "?"
    if len(testo) <= max_chars:
        return [testo]
    lines, cur, troncato = [], "", False
    for word in testo.split(" "):
        # parola singola più lunga di una riga → taglio netto
        while len(word) > max_chars and not troncato:
            if cur:
                if len(lines) >= max_lines:
                    troncato = True
                    break
                lines.append(cur)
                cur = ""
            if len(lines) >= max_lines:
                troncato = True
                break
            lines.append(word[:max_chars])
            word = word[max_chars:]
        if troncato:
            break
        cand = word if not cur else cur + " " + word
        if len(cand) <= max_chars:
            cur = cand
        elif len(lines) >= max_lines:
            troncato = True
            break
        else:
            lines.append(cur)
            cur = word
    if not troncato and cur:
        if len(lines) < max_lines:
            lines.append(cur)
        else:
            troncato = True
    if not lines:
        lines = [testo[:max_chars]]
        troncato = len(testo) > max_chars
    if troncato:
        lines[-1] = lines[-1][:max_chars - 1].rstrip() + "…"
    return lines[:max_lines]


def _render_nome(canvas, cx, lines, size, fill, emoji_imgs, primo_centro_y):
    """Disegna le righe di un nome impilate verticalmente, centrate su cx."""
    lh = size + 4
    for i, line in enumerate(lines):
        _testo_centrato(canvas, cx, int(primo_centro_y + i * lh), line, size, fill, emoji_imgs)


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return (
        0x1F000 <= o <= 0x1FAFF or   # emoji vari
        0x2600 <= o <= 0x27BF or     # simboli misc / dingbat
        0x2300 <= o <= 0x23FF or     # simboli tecnici (⏱ ecc.)
        0x2B00 <= o <= 0x2BFF or     # stelle/frecce (⭐ ➡)
        0x2190 <= o <= 0x21FF or     # frecce
        0xFE00 <= o <= 0xFE0F or     # variation selector
        0x200D == o or               # zero width joiner
        o in (0x2764, 0x2049, 0x203C, 0x2122, 0x00A9, 0x00AE)
    )


def _segmenta(testo: str):
    """Spezza il testo in blocchi (testo normale / emoji)."""
    segmenti = []
    corrente = ""
    is_em = None
    for ch in testo:
        e = _is_emoji(ch)
        if corrente and e != is_em:
            segmenti.append((corrente, is_em))
            corrente = ""
        corrente += ch
        is_em = e
    if corrente:
        segmenti.append((corrente, is_em))
    return segmenti


def _testo_centrato(canvas: Image.Image, cx: int, cy: int, testo: str, size: int,
                    fill, emoji_imgs=None, shadow=True, bold=True):
    """Disegna testo + emoji a colori, centrato su (cx, cy).

    Niente contorno nero: solo un'ombra morbida per la leggibilità (stile ZeroTwo).
    Se `emoji_imgs` contiene il segmento emoji, usa la Twemoji (uguale a Discord).
    """
    draw = ImageDraw.Draw(canvas)
    normale = _font(size, bold=bold)
    target_h = int(size * 0.9)
    emoji_imgs = emoji_imgs or {}

    parti = []  # (tipo, contenuto, larghezza)
    totale = 0
    for s, e in _segmenta(testo):
        if e:
            tw = emoji_imgs.get(s)
            img = tw.resize((target_h, target_h), Image.LANCZOS) if tw is not None else _render_emoji(s, target_h)
            if img:
                parti.append(("emoji", img, img.width))
                totale += img.width
        else:
            w = normale.getlength(s)
            parti.append(("testo", s, w))
            totale += w

    x = cx - totale / 2
    for tipo, cont, w in parti:
        if tipo == "emoji":
            canvas.alpha_composite(cont, (int(x), int(cy - cont.height / 2)))
        else:
            if shadow:
                draw.text((x + 2, cy + 2), cont, font=normale, anchor="lm", fill=(0, 0, 0))
            draw.text((x, cy), cont, font=normale, anchor="lm", fill=fill)
        x += w


def misura_testo_font(testo: str, size: int, bold: bool = True) -> float:
    normale = _font(size, bold=bold)
    target_h = int(size * 0.9)
    tot = 0
    for s, e in _segmenta(testo):
        if e:
            tot += target_h * max(1, len(s))  # emoji ~ quadrate
        else:
            tot += normale.getlength(s)
    return tot


def _petalo(size: int, color) -> Image.Image:
    """Disegna un singolo petalo di sakura."""
    p = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.ellipse([size * 0.28, size * 0.05, size * 0.72, size * 0.95], fill=color)
    # piccola tacca in punta per dare la forma a cuore del petalo
    d.polygon([(size * 0.5, size * 0.05), (size * 0.4, size * 0.22),
               (size * 0.6, size * 0.22)], fill=(0, 0, 0, 0))
    return p


def _genera_sfondo() -> Image.Image:
    # Se esiste un'immagine personalizzata, usala (ritagliata a misura)
    if os.path.exists(SFONDO_PERSONALIZZATO):
        try:
            img = Image.open(SFONDO_PERSONALIZZATO).convert("RGBA")
            # ridimensiona mantenendo le proporzioni e ritaglia al centro
            scala = max(W / img.width, H / img.height)
            img = img.resize((int(img.width * scala), int(img.height * scala)))
            sx = (img.width - W) // 2
            sy = (img.height - H) // 2
            return img.crop((sx, sy, sx + W, sy + H))
        except Exception:
            pass  # se fallisce, ripiega sullo sfondo generato

    return _genera_sfondo_giappone()


def _nuvola(draw, x, y, s):
    bianco = (255, 255, 255, 230)
    for dx, dy, r in [(0, 0, s), (s * 0.7, s * 0.15, s * 0.75), (-s * 0.7, s * 0.15, s * 0.7),
                      (s * 0.35, -s * 0.25, s * 0.6), (-s * 0.35, -s * 0.2, s * 0.55)]:
        draw.ellipse([x + dx - r, y + dy - r, x + dx + r, y + dy + r], fill=bianco)


def _genera_sfondo_giappone() -> Image.Image:
    rng = random.Random(7)
    HORIZON = 285

    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)

    # Cielo: azzurro intenso in alto -> chiaro all'orizzonte
    cielo_alto = (58, 140, 222)
    cielo_basso = (170, 215, 245)
    for y in range(HORIZON):
        t = y / HORIZON
        r = int(cielo_alto[0] * (1 - t) + cielo_basso[0] * t)
        g = int(cielo_alto[1] * (1 - t) + cielo_basso[1] * t)
        b = int(cielo_alto[2] * (1 - t) + cielo_basso[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    bg = bg.convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # Bagliore del sole in alto a sinistra
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(140, 0, -10):
        a = int(60 * (1 - r / 140))
        gd.ellipse([120 - r, 70 - r, 120 + r, 70 + r], fill=(255, 250, 210, a))
    bg = Image.alpha_composite(bg, glow)
    draw = ImageDraw.Draw(bg)

    # Nuvole
    for _ in range(5):
        _nuvola(draw, rng.randint(80, W - 80), rng.randint(40, 150), rng.randint(22, 38))

    # Monte Fuji
    cx_m = W // 2 + 40
    peak = (cx_m, 110)
    base_l = (cx_m - 250, HORIZON)
    base_r = (cx_m + 250, HORIZON)
    draw.polygon([peak, base_l, base_r], fill=(120, 138, 175))
    # ombreggiatura lato destro
    draw.polygon([peak, (cx_m, HORIZON), base_r], fill=(104, 122, 160))
    # neve in cima
    draw.polygon([(cx_m, 110), (cx_m - 60, 168), (cx_m - 35, 158), (cx_m - 15, 172),
                  (cx_m + 12, 156), (cx_m + 38, 170), (cx_m + 60, 168)], fill=(245, 248, 255))

    # Colline lontane (foschia) all'orizzonte
    for cx_h, w_h, col in [(120, 220, (150, 190, 200)), (650, 260, (140, 182, 195)),
                           (400, 300, (160, 198, 208))]:
        draw.ellipse([cx_h - w_h, HORIZON - 55, cx_h + w_h, HORIZON + 80], fill=col)

    # Città lontana (silhouette di palazzi)
    rng_city = random.Random(3)
    for bx in range(180, 620, 16):
        bh = rng_city.randint(12, 40)
        draw.rectangle([bx, HORIZON - bh, bx + 11, HORIZON], fill=(170, 175, 195))

    # Prato in primo piano (gradiente verde)
    erba_alto = (138, 205, 92)
    erba_basso = (70, 150, 55)
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        r = int(erba_alto[0] * (1 - t) + erba_basso[0] * t)
        g = int(erba_alto[1] * (1 - t) + erba_basso[1] * t)
        b = int(erba_alto[2] * (1 - t) + erba_basso[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Ramo di sakura in alto (angolo sinistro)
    marrone = (90, 55, 40)
    draw.line([(-10, 10), (240, 70)], fill=marrone, width=10)
    draw.line([(70, 25), (110, 95)], fill=marrone, width=5)
    draw.line([(160, 48), (200, 110)], fill=marrone, width=5)
    # Grappoli di fiori rosa
    rosa_fiori = [(255, 183, 213), (255, 160, 200), (255, 205, 225), (255, 150, 195)]
    for _ in range(70):
        fx = rng.randint(0, 250)
        fy = int(10 + (fx / 250) * 60 + rng.randint(-30, 45))
        r = rng.randint(5, 11)
        draw.ellipse([fx - r, fy - r, fx + r, fy + r], fill=rng.choice(rosa_fiori))

    # Petali che cadono
    for _ in range(22):
        size = rng.randint(12, 24)
        col = rng.choice(rosa_fiori) + (rng.randint(180, 235),)
        petalo = _petalo(size, col).rotate(rng.randint(0, 360), expand=True)
        bg.alpha_composite(petalo, (rng.randint(0, W - 10), rng.randint(0, H - 10)))

    return bg


def _draw_heart(draw: ImageDraw.ImageDraw, cx: float, cy: float, larghezza: float, color):
    """Disegna un vero cuore usando la curva parametrica classica."""
    scala = larghezza / 32.0  # la curva ha x in [-16, 16]
    punti = []
    t = 0.0
    while t < 2 * math.pi:
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        punti.append((cx + x * scala, cy - y * scala))
        t += 0.15
    draw.polygon(punti, fill=color)


async def _fetch_twemoji(session, emoji: str):
    """Scarica (e mette in cache) la Twemoji per un segmento emoji. None se fallisce."""
    name = "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)
    if not name:
        return None
    try:
        os.makedirs(_EMOJI_DIR, exist_ok=True)
        path = os.path.join(_EMOJI_DIR, f"{name}.png")
        if os.path.exists(path):
            return Image.open(path).convert("RGBA")
        url = f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72/{name}.png"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            data = await r.read()
        with open(path, "wb") as f:
            f.write(data)
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


async def _prefetch_emoji(*names):
    """Pre-scarica le Twemoji presenti nei nomi (così il rendering nel thread è sincrono)."""
    segs = set()
    for n in names:
        for s, e in _segmenta(_normalizza_nome(n)):
            if e:
                segs.add(s)
    imgs = {}
    if not segs:
        return imgs
    try:
        async with aiohttp.ClientSession() as session:
            for s in segs:
                img = await _fetch_twemoji(session, s)
                if img:
                    imgs[s] = img
    except Exception:
        pass
    return imgs


def _crea_immagine(av1_bytes: bytes, av2_bytes: bytes, perc: int, name1: str, name2: str,
                   emoji_imgs=None) -> io.BytesIO:
    name1 = _normalizza_nome(name1)
    name2 = _normalizza_nome(name2)
    canvas = _genera_sfondo()
    draw = ImageDraw.Draw(canvas)

    av1 = Image.open(io.BytesIO(av1_bytes)).convert("RGBA").resize((190, 190))
    av2 = Image.open(io.BytesIO(av2_bytes)).convert("RGBA").resize((190, 190))

    box = 190
    bordo = 3
    y = (H - box) // 2
    x1 = 110
    x2 = W - 110 - box

    for ax, av in ((x1, av1), (x2, av2)):
        draw.rectangle([ax - bordo, y - bordo, ax + box + bordo, y + box + bordo], fill=ROSA)
        canvas.paste(av, (ax, y), av)

    # Nomi: rosa, interi (su 2 righe se lunghi), senza contorno nero — stile ZeroTwo
    lines1 = _wrap_nome(name1)
    lines2 = _wrap_nome(name2)
    lh = 34
    _render_nome(canvas, int(x1 + box / 2), lines1, 30, ROSA, emoji_imgs, y + box + 25)
    primo2 = (y - 25) - (len(lines2) - 1) * lh
    _render_nome(canvas, int(x2 + box / 2), lines2, 30, ROSA, emoji_imgs, primo2)

    # Cuore centrale con percentuale (un decimale, stile ZeroTwo)
    cx, cy = W // 2, H // 2
    _draw_heart(draw, cx, cy, 130, ROSA)
    draw.text((cx, cy + 6), f"{perc}%", font=_font(26), fill=(90, 25, 55), anchor="mm")

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


class PairConfirmView(discord.ui.View):
    """Richiesta di conferma: l'altra persona deve accettare entro 60 secondi."""
    def __init__(self, proponente: discord.Member, partner: discord.Member, guild_id: int):
        super().__init__(timeout=60)
        self.proponente = proponente
        self.partner = partner
        self.guild_id = guild_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.partner.id:
            await interaction.response.send_message(
                _t(interaction, "fun.only_target"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accetta", emoji="💍", style=discord.ButtonStyle.success)
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        db.add_marriage(self.guild_id, self.proponente.id, self.partner.id, hours=24)
        for it in self.children:
            it.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content=t(db.get_log_config(self.guild_id), "fun.married", a=self.proponente.mention, b=self.partner.mention),
            view=self)

    async def on_timeout(self):
        if self.message:
            for it in self.children:
                it.disabled = True
            try:
                await self.message.edit(
                    content=t(db.get_log_config(self.guild_id), "fun.timeout", user=self.partner.mention),
                    view=self)
            except (discord.HTTPException, discord.NotFound):
                pass


class PairView(discord.ui.View):
    def __init__(self, u1: discord.Member, u2: discord.Member, guild_id: int):
        super().__init__(timeout=180)
        self.u1 = u1
        self.u2 = u2
        self.guild_id = guild_id

    @discord.ui.button(label="Pair", emoji="💍", style=discord.ButtonStyle.success)
    async def pair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.u1.id == self.u2.id:
            await interaction.response.send_message(
                "💍 Non puoi sposare te stesso! L'autostima è importante, "
                "ma per sposarti serve qualcun altro 😄", ephemeral=True)
            return
        if interaction.user.id not in (self.u1.id, self.u2.id):
            await interaction.response.send_message(
                "❌ Solo le due persone shippate possono sposarsi!", ephemeral=True
            )
            return

        proponente = interaction.user
        partner = self.u2 if proponente.id == self.u1.id else self.u1

        # Controlla che il partner accetti entro 60 secondi
        confirm = PairConfirmView(proponente, partner, self.guild_id)
        await interaction.response.send_message(
            content=f"{partner.mention}, **{proponente.display_name}** vuole sposarti! 💍\n"
                    f"Accetti entro **60 secondi**?",
            view=confirm)
        confirm.message = await interaction.original_response()


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        if not logconfig.feature_enabled(db.get_log_config(ctx.guild.id), "fun"):
            await ctx.send(_t(ctx, "fun.disabled"))
            return False
        return True

    # ── SHIP ──────────────────────────────────────────────────────────────────
    @commands.command(name="ship")
    async def ship(self, ctx: commands.Context, utente1: discord.Member,
                   utente2: discord.Member = None):
        if utente2 is None:
            utente2 = ctx.author
        await ctx.typing()

        # Percentuale deterministica per coppia E per giorno: cambia ogni notte a mezzanotte
        coppia = tuple(sorted([utente1.id, utente2.id]))
        giorno = datetime.datetime.now().date()
        rng = random.Random(hash((coppia, giorno.isoformat())))
        perc = round(rng.uniform(0, 100), 1)

        # Frasi varie: i nomi non sono sempre all'inizio. {a} e {b} = i due utenti
        cfg_ship = db.get_log_config(ctx.guild.id)
        tier = ("fun.ship_t0" if perc < 20 else "fun.ship_t1" if perc < 40 else
                "fun.ship_t2" if perc < 60 else "fun.ship_t3" if perc < 80 else
                "fun.ship_t4" if perc < 95 else "fun.ship_t5")
        frasi = tlist(cfg_ship, tier)
        commento = random.choice(frasi).format(a=utente1.mention, b=utente2.mention)

        # Genera l'immagine (in un thread per non bloccare il bot)
        av1_bytes = await utente1.display_avatar.replace(size=256).read()
        av2_bytes = await utente2.display_avatar.replace(size=256).read()
        emoji_imgs = await _prefetch_emoji(utente1.display_name, utente2.display_name)
        buf = await asyncio.to_thread(
            _crea_immagine, av1_bytes, av2_bytes, perc,
            utente1.display_name, utente2.display_name, emoji_imgs,
        )

        file = discord.File(buf, filename="ship.png")
        view = PairView(utente1, utente2, ctx.guild.id)
        await ctx.send(content=commento, file=file, view=view)

    # ── MARRIAGE ──────────────────────────────────────────────────────────────
    @commands.command(name="marriage")
    async def marriage(self, ctx: commands.Context, utente: discord.Member = None):
        target = utente or ctx.author
        m = db.get_marriage(ctx.guild.id, target.id)

        if not m:
            await ctx.send(_t(ctx, "fun.single", user=target.mention))
            return

        scadenza = datetime.datetime.fromisoformat(m["expires_at"])
        quando = discord.utils.format_dt(scadenza, style="R")

        embed = discord.Embed(title=_t(ctx, "fun.marriage_title"), color=0xFF6B9D)
        embed.add_field(name=_t(ctx, "fun.marriage_couple"), value=f"<@{m['user1']}> 💞 <@{m['user2']}>", inline=False)
        embed.add_field(name=_t(ctx, "fun.marriage_expires"), value=quando, inline=False)
        embed.set_footer(text="I matrimoni durano 24 ore")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
