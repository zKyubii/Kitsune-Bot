import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import io
import os
import math
import datetime
from PIL import Image, ImageDraw, ImageFont

import database as db
import logconfig

ROSA = (255, 140, 200)
W, H = 800, 450

# Se metti un'immagine qui, verrà usata come sfondo al posto di quello generato
SFONDO_PERSONALIZZATO = os.path.join(os.path.dirname(__file__), "..", "assets", "ship_bg.png")


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


def _font_emoji(size: int):
    f = _carica(_FONT_EMOJI, size)
    if f is None:
        # Noto Color Emoji su Linux ha una sola dimensione bitmap (109px)
        for p in _FONT_EMOJI:
            try:
                return ImageFont.truetype(p, 109)
            except Exception:
                continue
    return f


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
                    fill, stroke_fill=(0, 0, 0), stroke_width=2, bold=True):
    """Disegna testo + emoji a colori, centrato orizzontalmente su (cx, cy)."""
    draw = ImageDraw.Draw(canvas)
    normale = _font(size, bold=bold)
    emoji = _font_emoji(size)

    segmenti = _segmenta(testo)
    larghezze = []
    totale = 0
    for s, e in segmenti:
        f = emoji if (e and emoji) else normale
        w = f.getlength(s)
        larghezze.append(w)
        totale += w

    x = cx - totale / 2
    for (s, e), w in zip(segmenti, larghezze):
        if e and emoji:
            draw.text((x, cy), s, font=emoji, anchor="lm", embedded_color=True)
        else:
            draw.text((x, cy), s, font=normale, anchor="lm", fill=fill,
                      stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += w


def misura_testo_font(testo: str, size: int, bold: bool = True) -> float:
    normale = _font(size, bold=bold)
    emoji = _font_emoji(size)
    tot = 0
    for s, e in _segmenta(testo):
        f = emoji if (e and emoji) else normale
        tot += f.getlength(s)
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


def _crea_immagine(av1_bytes: bytes, av2_bytes: bytes, perc: int, name1: str, name2: str) -> io.BytesIO:
    canvas = _genera_sfondo()
    draw = ImageDraw.Draw(canvas)

    av1 = Image.open(io.BytesIO(av1_bytes)).convert("RGBA").resize((190, 190))
    av2 = Image.open(io.BytesIO(av2_bytes)).convert("RGBA").resize((190, 190))

    box = 190
    bordo = 6
    y = (H - box) // 2
    x1 = 110
    x2 = W - 110 - box

    for ax, av in ((x1, av1), (x2, av2)):
        draw.rectangle([ax - bordo, y - bordo, ax + box + bordo, y + box + bordo], fill=ROSA)
        canvas.paste(av, (ax, y), av)

    # Nomi (con emoji a colori)
    _testo_centrato(canvas, int(x1 + box / 2), int(y + box + 30), name1[:20], 30, ROSA)
    _testo_centrato(canvas, int(x2 + box / 2), int(y - 30), name2[:20], 30, ROSA)

    # Cuore centrale con percentuale
    cx, cy = W // 2, H // 2
    _draw_heart(draw, cx, cy, 130, ROSA)
    draw.text((cx, cy + 6), f"{perc}%", font=_font(28), fill=(90, 25, 55), anchor="mm")

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


class PairView(discord.ui.View):
    def __init__(self, u1: discord.Member, u2: discord.Member, guild_id: int):
        super().__init__(timeout=180)
        self.u1 = u1
        self.u2 = u2
        self.guild_id = guild_id

    @discord.ui.button(label="Pair", emoji="💍", style=discord.ButtonStyle.success)
    async def pair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.u1.id, self.u2.id):
            await interaction.response.send_message(
                "❌ Solo le due persone shippate possono sposarsi!", ephemeral=True
            )
            return

        db.add_marriage(self.guild_id, self.u1.id, self.u2.id, hours=24)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"💍 {self.u1.mention} e {self.u2.mention} si sono sposati per **24 ore**! 🎉💕"
        )


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, logconfig.FeatureDisabled):
            msg = "🚫 La funzione Fun è disattivata su questo server."
        else:
            msg = f"❌ Errore: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── SHIP ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="ship", description="Calcola la compatibilità amorosa tra due persone")
    @app_commands.describe(
        utente1="La prima persona",
        utente2="(Opzionale) La seconda persona — se vuoto, sei tu",
    )
    @logconfig.feature_check("fun")
    async def ship(self, interaction: discord.Interaction, utente1: discord.Member,
                   utente2: discord.Member = None):
        if utente2 is None:
            utente2 = interaction.user

        await interaction.response.defer()

        # Percentuale deterministica per coppia E per giorno: cambia ogni notte a mezzanotte
        coppia = tuple(sorted([utente1.id, utente2.id]))
        giorno = datetime.datetime.now().date()
        rng = random.Random(hash((coppia, giorno.isoformat())))
        perc = rng.randint(0, 100)

        # Frasi random in stile ZeroTwo (con le menzioni). {a} e {b} = i due utenti
        if perc < 20:
            frasi = [
                "Ahia... {a} & {b}, sarà un disastro 💀",
                "Rischioso, {a} & {b}, non ci scommetterei 😬",
                "Ehm, {a} & {b}, forse è meglio lasciar perdere 🙈",
                "{a} & {b}, le stelle dicono: scappate 🏃💨",
            ]
        elif perc < 40:
            frasi = [
                "Mmh, {a} & {b}, potrebbe andare peggio 😅",
                "{a} & {b}, c'è qualcosina ma non troppo 🤏",
                "{a} & {b}, servirebbe un piccolo miracolo ✨",
                "{a} & {b}, partite con calma 🐌",
            ]
        elif perc < 60:
            frasi = [
                "{a} & {b}, potrebbe funzionare, chi lo sa 🤔",
                "Non male, {a} & {b}! C'è del potenziale 🙂",
                "{a} & {b}, siete a metà strada 💗",
                "{a} & {b}, qualche scintilla si vede 👀",
            ]
        elif perc < 80:
            frasi = [
                "{a} & {b}, ci siamo quasi! 💕",
                "Carini insieme, {a} & {b} 🥰",
                "{a} & {b}, l'amore è nell'aria 🌸",
                "{a} & {b}, bella coppia davvero 💘",
            ]
        elif perc < 95:
            frasi = [
                "{a} & {b}, siete fatti l'uno per l'altro 💞",
                "Sono sorpreso che non siate ancora sposati! {a} & {b} 💍",
                "{a} & {b}, una coppia da favola 🏰",
                "{a} & {b}, anime gemelle 🫶",
            ]
        else:
            frasi = [
                "Matrimonio in vista! {a} & {b} 💍🔥",
                "{a} & {b}, amore eterno scritto nelle stelle ⭐",
                "{a} & {b}, inseparabili per sempre ♾️❤️",
                "{a} & {b}, l'universo vi ha uniti 🌌",
            ]
        commento = random.choice(frasi).format(a=utente1.mention, b=utente2.mention)

        # Genera l'immagine (in un thread per non bloccare il bot)
        av1_bytes = await utente1.display_avatar.replace(size=256).read()
        av2_bytes = await utente2.display_avatar.replace(size=256).read()
        buf = await asyncio.to_thread(
            _crea_immagine, av1_bytes, av2_bytes, perc,
            utente1.display_name, utente2.display_name,
        )

        file = discord.File(buf, filename="ship.png")
        view = PairView(utente1, utente2, interaction.guild_id)
        await interaction.followup.send(content=commento, file=file, view=view)

    # ── MARRIAGE ──────────────────────────────────────────────────────────────
    @app_commands.command(name="marriage", description="Mostra con chi sei sposato/a (dura 24h)")
    @app_commands.describe(utente="(Opzionale) Controlla il matrimonio di un altro utente")
    @logconfig.feature_check("fun")
    async def marriage(self, interaction: discord.Interaction, utente: discord.Member = None):
        target = utente or interaction.user
        m = db.get_marriage(interaction.guild_id, target.id)

        if not m:
            await interaction.response.send_message(
                f"💔 {target.mention} al momento è single.", ephemeral=True
            )
            return

        scadenza = datetime.datetime.fromisoformat(m["expires_at"])
        quando = discord.utils.format_dt(scadenza, style="R")

        embed = discord.Embed(title="💍 Matrimonio", color=0xFF6B9D)
        embed.add_field(name="Coppia", value=f"<@{m['user1']}> 💞 <@{m['user2']}>", inline=False)
        embed.add_field(name="Scade", value=quando, inline=False)
        embed.set_footer(text="I matrimoni durano 24 ore")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
