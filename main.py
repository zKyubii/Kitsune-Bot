import discord
from discord.ext import commands
import os
import asyncio
import traceback
from dotenv import load_dotenv

import database as db

load_dotenv()
db.init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["+", "!"], intents=intents, help_command=None)


@bot.event
async def on_command_error(ctx, error):
    # Ignora i comandi inesistenti (es. "+quote" gestito dal listener) e i check falliti
    if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Manca un argomento. Prova `+help {ctx.command}`.")
        return
    if isinstance(error, (commands.BadArgument, commands.MemberNotFound)):
        await ctx.send("❌ Argomento non valido (controlla che l'utente esista).")
        return
    traceback.print_exception(type(error), error, error.__traceback__)


@bot.event
async def on_ready():
    print(f"✅ Bot online come {bot.user}")

    # ── STATO DEL BOT ──────────────────────────────────────────────────────
    # Il testo dello status si imposta da .env con BOT_STATUS (vuoto = nessuno).
    # Per altri tipi di attività al posto di CustomActivity:
    #   discord.Game(name="...")                                         → "Sta giocando a ..."
    #   discord.Activity(type=discord.ActivityType.watching, name="...") → "Guarda ..."
    #   discord.Activity(type=discord.ActivityType.listening, name="...")→ "Ascolta ..."
    # Status (pallino): online / idle / dnd / invisible
    status_text = os.getenv("BOT_STATUS", "").strip()
    if status_text:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.CustomActivity(name=status_text),
        )

    try:
        guild_ids = [g.strip() for g in os.getenv("GUILD_ID", "").split(",") if g.strip()]
        if guild_ids:
            # Sync istantanea su ogni server elencato
            for gid in guild_ids:
                guild = discord.Object(id=int(gid))
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                print(f"⚡ Sincronizzati {len(synced)} comandi sul server {gid} (istantaneo)")
            # Svuota i comandi globali per evitare i doppioni
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
        else:
            synced = await bot.tree.sync()
            print(f"⚡ Sincronizzati {len(synced)} comandi slash (globale)")
    except Exception as e:
        print(f"❌ Errore sync comandi: {e}")

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"📦 Caricato: {filename}")

async def main():
    await load_cogs()
    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
