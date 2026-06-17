import discord
from discord.ext import commands

ORO = 0xF1C40F

TITOLO = "📖 Comandi Kitsune"
INTRO = (
    "Ecco la lista dei comandi disponibili.\n"
    "Usa il prefix, slash o context menu in base al comando.\n"
    "Mini-help rapido: `+help <comando>`."
)

# Pagine: ogni pagina è una lista di (categoria, [(etichetta, descrizione), ...])
PAGINE = [
    [
        ("Utility", [
            ("`+av` | `+avuser`", "Avatar del server / del profilo di un utente."),
            ("`+banner` | `+banneruser`", "Banner del server / del profilo di un utente."),
            ("`+quote`", "Rispondi a un messaggio e scrivi `+quote` per farne una citazione."),
            ("`+help`", "Mostra questa lista (o `+help <comando>` per i dettagli)."),
        ]),
        ("Minigiochi", [
            ("`+rps <sasso/carta/forbice>`", "Sasso carta forbice contro il bot."),
            ("`+ship @utente1 <@utente2>`", "Compatibilità amorosa tra due utenti."),
            ("`+8ball <domanda>`", "Fai una domanda alla palla magica."),
            ("`+moneta <testa/croce>`", "Scegli e lancia la moneta."),
            ("`+indovina`", "Indovina il numero tra 1 e 100 (`+tentativo <n>`)."),
            ("`+marriage <@utente>`", "Mostra con chi sei sposato/a (dura 24h)."),
        ]),
        ("Level", [
            ("`+rank` | `+r`", "Mostra il tuo livello (o altrui) e la posizione in classifica."),
            ("`+leaderboard` | `+lb`", "Classifica livelli del server (top 10)."),
        ]),
    ],
]

# Dettaglio per +help <comando>
DETTAGLI = {
    "av": ("`+av <@utente>`", "Mostra l'avatar che hai (o un altro utente) nel server."),
    "avuser": ("`+avuser <@utente>`", "Mostra l'avatar del profilo (globale)."),
    "banner": ("`+banner <@utente>`", "Mostra il banner del server o, se non c'è, del profilo."),
    "banneruser": ("`+banneruser <@utente>`", "Mostra il banner del profilo (globale)."),
    "quote": ("`+quote` (in risposta)", "Rispondi a un messaggio con `+quote` per trasformarlo in citazione."),
    "help": ("`+help [comando]`", "Mostra tutti i comandi, o i dettagli di uno specifico."),
    "rps": ("`+rps <sasso/carta/forbice>`", "Sasso carta forbice contro il bot."),
    "ship": ("`+ship @utente1 <@utente2>`", "Compatibilità amorosa tra due utenti (taggane 1 o 2)."),
    "8ball": ("`+8ball <domanda>`", "Fai una domanda alla palla magica."),
    "moneta": ("`+moneta <testa/croce>`", "Scegli testa o croce e lancia la moneta."),
    "indovina": ("`+indovina` / `+tentativo <n>`", "Indovina il numero tra 1 e 100."),
    "tentativo": ("`+tentativo <numero>`", "Prova a indovinare il numero della partita in corso."),
    "marriage": ("`+marriage <@utente>`", "Mostra con chi sei sposato/a (dura 24h)."),
    "rank": ("`+rank` / `+r <@utente>`", "Mostra il tuo livello (o altrui) e la posizione in classifica."),
    "r": ("`+r <@utente>`", "Alias di `+rank`: il tuo livello (o altrui) e la posizione."),
    "leaderboard": ("`+leaderboard` / `+lb`", "Classifica livelli del server (top 10)."),
    "lb": ("`+lb`", "Alias di `+leaderboard`: classifica del server (top 10)."),
}


def _embed_pagina(index: int) -> discord.Embed:
    # Tutto nella descrizione con markdown: titolo grande (#), categorie (###),
    # e una riga vuota tra un comando e l'altro per dare respiro.
    parti = [f"# {TITOLO}", "", INTRO, ""]
    for categoria, comandi in PAGINE[index]:
        parti.append(f"### {categoria}")
        righe = [f"• {etichetta} — {descr}" for etichetta, descr in comandi]
        parti.append("\n\n".join(righe))
        parti.append("")
    embed = discord.Embed(description="\n".join(parti), color=ORO)
    if len(PAGINE) > 1:
        embed.set_footer(text=f"Pagina {index + 1}/{len(PAGINE)}")
    return embed


class HelpView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.index = 0
        self.message = None
        self._aggiorna()

    def _aggiorna(self):
        self.prev.disabled = self.index == 0
        self.next.disabled = self.index >= len(PAGINE) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo chi ha aperto l'help può sfogliarlo.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._aggiorna()
        await interaction.response.edit_message(embed=_embed_pagina(self.index), view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(PAGINE) - 1, self.index + 1)
        self._aggiorna()
        await interaction.response.edit_message(embed=_embed_pagina(self.index), view=self)

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        if self.message:
            for it in self.children:
                it.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context, *, comando: str = None):
        if comando:
            chiave = comando.strip().lstrip("+").lower()
            d = DETTAGLI.get(chiave)
            if not d:
                await ctx.send(f"❌ Comando `{comando}` non trovato. Usa `+help` per la lista.")
                return
            uso, descr = d
            embed = discord.Embed(title=f"Comando: {chiave}", color=ORO,
                                  description=f"{uso}\n\n{descr}")
            await ctx.send(embed=embed)
            return
        view = HelpView(ctx.author.id)
        view.message = await ctx.send(embed=_embed_pagina(0), view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))
