import asyncio
import re

import discord
from discord.ext import commands

import database as db
import logconfig

# Solo numeri interi positivi: qualsiasi altro messaggio viene ignorato,
# non conta come errore (così chi scrive due parole non rompe la catena).
_NUM_RE = re.compile(r"^\d+$")


# Traguardi di default: si personalizzano dalla dashboard, e svuotandoli si
# disattivano del tutto.
DEFAULT_MILESTONES = {"100": "💯", "1000": "🔥"}


def milestones_of(cnt: dict) -> dict:
    """{numero(str): emoji} — assente = default, vuoto = disattivati."""
    return cnt.get("milestones", DEFAULT_MILESTONES)


def _milestone_emoji(cnt: dict, numero: int):
    return milestones_of(cnt).get(str(numero))


def parse_milestones(testo: str) -> dict:
    """Legge righe tipo '100: 💯, 1000: 🔥' (i separatori sono liberi)."""
    out = {}
    for pezzo in re.split(r"[,\n]+", testo or ""):
        m = re.match(r"\s*(\d+)\s*[:=]?\s*(.+?)\s*$", pezzo)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Un lock per server: i numeri vanno validati in sequenza, altrimenti
        # due messaggi inviati nello stesso istante possono essere accettati
        # entrambi contro lo stesso numero atteso.
        self._locks = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        config = db.get_log_config(message.guild.id)
        if not logconfig.feature_enabled(config, "counting"):
            return
        cnt = config.get("counting", {})
        canale = cnt.get("channel")
        if not canale or message.channel.id != canale:
            return
        testo = message.content.strip()
        if not _NUM_RE.match(testo):
            return
        async with self._lock(message.guild.id):
            await self._valuta(message, int(testo))

    async def _valuta(self, message: discord.Message, numero: int):
        # Rileggiamo la config dentro il lock: potrebbe essere cambiata
        # mentre aspettavamo il nostro turno.
        config = db.get_log_config(message.guild.id)
        cnt = config.setdefault("counting", {})
        atteso = cnt.get("current", 0) + 1
        stesso_utente = cnt.get("last_user") == message.author.id

        if numero != atteso or stesso_utente:
            await self._fallimento(message, config, cnt, stesso_utente, atteso)
            return

        cnt["current"] = numero
        cnt["last_user"] = message.author.id
        # Ci serve per riconoscere la cancellazione dell'ultimo numero anche
        # quando il messaggio non è più nella cache del bot.
        cnt["last_message_id"] = message.id
        if numero > cnt.get("record", 0):
            cnt["record"] = numero
        db.save_log_config(message.guild.id, config)

        if cnt.get("react_ok", True):
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass

        # I traguardi si festeggiano anche con la spunta disattivata: sono rari
        # ed è il momento "premio". Si configurano (o si spengono) da dashboard.
        traguardo = _milestone_emoji(cnt, numero)
        if traguardo:
            try:
                await message.add_reaction(traguardo)
            except discord.HTTPException:
                pass

    async def _fallimento(self, message, config, cnt, stesso_utente, atteso):
        # Modalità morbida: il conteggio non si azzera, si toglie solo il
        # messaggio sbagliato.
        if not cnt.get("reset_on_fail", True):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            return

        raggiunto = cnt.get("current", 0)
        record = cnt.get("record", 0)
        cnt["current"] = 0
        cnt["last_user"] = None
        cnt["last_message_id"] = None
        db.save_log_config(message.guild.id, config)

        try:
            await message.add_reaction("❌")
        except discord.HTTPException:
            pass

        motivo = ("non puoi contare due volte di fila"
                  if stesso_utente else f"il numero giusto era **{atteso}**")
        try:
            await message.channel.send(
                f"❌ {message.author.mention} ha rotto la catena: {motivo}.\n"
                f"Si riparte da **1** — eravate arrivati a **{raggiunto}** · record **{record}**"
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Avvisa quando qualcuno cancella l'ultimo numero valido.

        Il numero resta valido (la catena non si rompe): serve solo a far
        capire a tutti qual è il prossimo numero, visto che è sparito.
        """
        if payload.guild_id is None:
            return
        config = db.get_log_config(payload.guild_id)
        if not logconfig.feature_enabled(config, "counting"):
            return
        cnt = config.get("counting", {})
        if payload.channel_id != cnt.get("channel"):
            return
        if not cnt.get("last_message_id") or payload.message_id != cnt["last_message_id"]:
            return

        canale = self.bot.get_channel(payload.channel_id)
        if canale is None:
            return
        numero = cnt.get("current", 0)
        uid = cnt.get("last_user")
        autore = f"<@{uid}>" if uid else "Qualcuno"
        try:
            await canale.send(
                f"⚠️ {autore} ha cancellato il suo numero: ```{numero}```"
                f"Il prossimo numero è **{numero + 1}**.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Counting(bot))
