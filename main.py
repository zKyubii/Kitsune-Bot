import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

import database as db

load_dotenv()
db.init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot online come {bot.user}")

    # ── STATO DEL BOT ──────────────────────────────────────────────────────
    # Cambia il testo e il tipo come preferisci. Tipi disponibili:
    #   discord.Game(name="...")                                         → "Sta giocando a ..."
    #   discord.Activity(type=discord.ActivityType.watching, name="...") → "Guarda ..."
    #   discord.Activity(type=discord.ActivityType.listening, name="...")→ "Ascolta ..."
    #   discord.CustomActivity(name="...")                               → testo libero
    # Status (pallino): online / idle / dnd / invisible
    attivita = discord.Activity(type=discord.ActivityType.watching, name=".gg/haizen")
    await bot.change_presence(status=discord.Status.online, activity=attivita)

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
