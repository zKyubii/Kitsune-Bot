import discord
from discord.ext import commands

import database as db
from locales import t

ORO = 0xF1C40F

TITOLO = "help.comandi_kitsune"
INTRO = "help.intro"

# Pagine: ogni pagina è una lista di (categoria, [(etichetta, descrizione), ...])
PAGINE = [
    [
        ("help.utility", [
            ("`+av` | `+avuser`", "help.avatar_server_profilo_utente"),
            ("`+banner` | `+banneruser`", "help.banner_server_profilo_utente"),
            ("`+quote`", "help.rispondi_messaggio_scrivi_quote_farne"),
            ("`+profile`", "help.apri_tuo_profilo_privacy_ruoli"),
            ("`+help`", "help.mostra_questa_lista_help_comando"),
        ]),
        ("help.minigiochi", [
            ("`+rps <rock/paper/scissors>`", "help.sasso_carta_forbice_contro_bot"),
            ("`+ship @user1 <@user2>`", "help.compatibilita_amorosa_tra_due_utenti"),
            ("`+8ball <question>`", "help.fai_domanda_alla_palla_magica"),
            ("`+moneta <heads/tails>`", "help.scegli_lancia_moneta"),
            ("`+indovina`", "help.indovina_numero_tra_1_100"),
            ("`+marriage <@user>`", "help.mostra_chi_sei_sposato_dura"),
        ]),
        ("help.level", [
            ("`+rank` | `+r`", "help.mostra_tuo_livello_altrui_posizione"),
            ("`+leaderboard` | `+lb`", "help.classifica_livelli_server_top_10"),
        ]),
    ],
]

# Dettaglio per +help <comando>
DETTAGLI = {
    "av": ("`+av <@user>`", "help.mostra_l_avatar_hai_altro"),
    "avuser": ("`+avuser <@user>`", "help.mostra_l_avatar_profilo_globale"),
    "banner": ("`+banner <@user>`", "help.mostra_banner_server_se_non"),
    "banneruser": ("`+banneruser <@user>`", "help.mostra_banner_profilo_globale"),
    "quote": ("`+quote` (as a reply)", "help.rispondi_messaggio_quote_trasformarlo_citazione"),
    "profile": ("`+profile <@user>`", "help.apri_tuo_profilo_privacy_avatar"),
    "profilo": ("`+profilo <@user>`", "help.alias_profile_apri_tuo_profilo"),
    "help": ("`+help [command]`", "help.mostra_tutti_comandi_dettagli_uno"),
    "rps": ("`+rps <rock/paper/scissors>`", "help.sasso_carta_forbice_contro_bot"),
    "ship": ("`+ship @user1 <@user2>`", "help.compatibilita_amorosa_tra_due_utenti2"),
    "8ball": ("`+8ball <question>`", "help.fai_domanda_alla_palla_magica"),
    "moneta": ("`+moneta <heads/tails>`", "help.scegli_testa_croce_lancia_moneta"),
    "indovina": ("`+indovina` / `+tentativo <n>`", "help.indovina_numero_tra_1_1002"),
    "tentativo": ("`+tentativo <number>`", "help.prova_indovinare_numero_partita_corso"),
    "marriage": ("`+marriage <@user>`", "help.mostra_chi_sei_sposato_dura"),
    "rank": ("`+rank` / `+r <@user>`", "help.mostra_tuo_livello_altrui_posizione"),
    "r": ("`+r <@user>`", "help.alias_rank_tuo_livello_altrui"),
    "leaderboard": ("`+leaderboard` / `+lb`", "help.classifica_livelli_server_top_10"),
    "lb": ("`+lb`", "help.alias_leaderboard_classifica_server_top"),
}


def _embed_pagina(index: int, config=None) -> discord.Embed:
    # Tutto nella descrizione con markdown: titolo grande (#), categorie (###),
    # e una riga vuota tra un comando e l'altro per dare respiro.
    # I testi sono chiavi: si risolvono qui nella lingua del server.
    parti = [f"# {t(config, TITOLO)}", "", t(config, INTRO), ""]
    for categoria, comandi in PAGINE[index]:
        parti.append(f"### {t(config, categoria)}")
        righe = [f"• {etichetta} — {t(config, descr)}" for etichetta, descr in comandi]
        parti.append("\n\n".join(righe))
        parti.append("")
    embed = discord.Embed(description="\n".join(parti), color=ORO)
    if len(PAGINE) > 1:
        embed.set_footer(text=t(config, "help.pagina", n=index + 1, tot=len(PAGINE)))
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
                t(db.get_log_config(interaction.guild_id), "help.only_author"), ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._aggiorna()
        await interaction.response.edit_message(embed=_embed_pagina(self.index, db.get_log_config(interaction.guild_id)), view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(PAGINE) - 1, self.index + 1)
        self._aggiorna()
        await interaction.response.edit_message(embed=_embed_pagina(self.index, db.get_log_config(interaction.guild_id)), view=self)

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
        config = db.get_log_config(ctx.guild.id) if ctx.guild else None
        if comando:
            chiave = comando.strip().lstrip("+").lower()
            d = DETTAGLI.get(chiave)
            if not d:
                await ctx.send(t(config, "help.non_trovato", cmd=comando))
                return
            uso, descr = d
            embed = discord.Embed(title=t(config, "help.comando_titolo", cmd=chiave), color=ORO,
                                  description=f"{uso}\n\n{t(config, descr)}")
            await ctx.send(embed=embed)
            return
        view = HelpView(ctx.author.id)
        view.message = await ctx.send(embed=_embed_pagina(0, config), view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))
