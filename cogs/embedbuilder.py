import discord
from discord.ext import commands
from discord import app_commands
import datetime

import database as db


def _replace(text, member, guild):
    if not text:
        return text
    if guild:
        text = text.replace("{server_name}", guild.name)
        text = text.replace("{server_membercount}", str(guild.member_count))
        text = text.replace("{server_icon}", guild.icon.url if guild.icon else "")
    if member:
        text = text.replace("{user}", member.mention)
        text = text.replace("{user_tag}", str(member))
        text = text.replace("{user_name}", member.name)
        text = text.replace("{user_avatar}", member.display_avatar.url)
        text = text.replace("{user_id}", str(member.id))
    return text


def _url_ok(u):
    return bool(u) and u.startswith("http")


def costruisci_embed(data: dict, member=None, guild=None) -> discord.Embed:
    e = discord.Embed()
    titolo = _replace(data.get("title", ""), member, guild)
    if titolo:
        e.title = titolo[:256]
    descr = _replace(data.get("description", ""), member, guild)
    if descr:
        e.description = descr[:4000]
    if data.get("color"):
        try:
            e.color = discord.Color(int(str(data["color"]).lstrip("#"), 16))
        except ValueError:
            pass

    author = data.get("author", {})
    a_name = _replace(author.get("name", ""), member, guild)
    if a_name:
        a_icon = _replace(author.get("icon", ""), member, guild)
        e.set_author(name=a_name[:256], icon_url=a_icon if _url_ok(a_icon) else None)

    footer = data.get("footer", {})
    f_text = _replace(footer.get("text", ""), member, guild)
    if f_text:
        f_icon = _replace(footer.get("icon", ""), member, guild)
        e.set_footer(text=f_text[:2048], icon_url=f_icon if _url_ok(f_icon) else None)

    img = _replace(data.get("image", ""), member, guild)
    if _url_ok(img):
        e.set_image(url=img)
    thumb = _replace(data.get("thumbnail", ""), member, guild)
    if _url_ok(thumb):
        e.set_thumbnail(url=thumb)

    if data.get("timestamp"):
        e.timestamp = datetime.datetime.now(datetime.timezone.utc)

    if not (e.title or e.description or a_name or f_text or _url_ok(img)):
        e.description = "*(embed vuoto — usa i bottoni qui sotto per modificarlo)*"
    return e


# ── MODALI ────────────────────────────────────────────────────────────────────
class BasicModal(discord.ui.Modal, title="Informazioni base"):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder
        d = builder.data
        self.titolo = discord.ui.TextInput(label="Titolo", default=d.get("title", ""),
                                           required=False, max_length=256)
        self.descr = discord.ui.TextInput(label="Descrizione", style=discord.TextStyle.paragraph,
                                          default=d.get("description", ""), required=False, max_length=4000)
        self.colore = discord.ui.TextInput(label="Colore (hex, es. 5865F2)", default=d.get("color", ""),
                                           required=False, max_length=7)
        self.add_item(self.titolo)
        self.add_item(self.descr)
        self.add_item(self.colore)

    async def on_submit(self, interaction):
        d = self.builder.data
        d["title"] = self.titolo.value
        d["description"] = self.descr.value
        d["color"] = self.colore.value
        await self.builder.refresh(interaction)


class AuthorModal(discord.ui.Modal, title="Autore"):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder
        a = builder.data.get("author", {})
        self.nome = discord.ui.TextInput(label="Nome autore", default=a.get("name", ""),
                                         required=False, max_length=256)
        self.icona = discord.ui.TextInput(label="URL icona autore", default=a.get("icon", ""),
                                          required=False)
        self.add_item(self.nome)
        self.add_item(self.icona)

    async def on_submit(self, interaction):
        self.builder.data["author"] = {"name": self.nome.value, "icon": self.icona.value}
        await self.builder.refresh(interaction)


class FooterModal(discord.ui.Modal, title="Footer"):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder
        f = builder.data.get("footer", {})
        self.testo = discord.ui.TextInput(label="Testo footer", default=f.get("text", ""),
                                          required=False, max_length=2048)
        self.icona = discord.ui.TextInput(label="URL icona footer", default=f.get("icon", ""),
                                          required=False)
        self.timestamp = discord.ui.TextInput(label="Timestamp? (yes/no)",
                                              default="yes" if builder.data.get("timestamp") else "no",
                                              required=False, max_length=3)
        self.add_item(self.testo)
        self.add_item(self.icona)
        self.add_item(self.timestamp)

    async def on_submit(self, interaction):
        self.builder.data["footer"] = {"text": self.testo.value, "icon": self.icona.value}
        self.builder.data["timestamp"] = self.timestamp.value.strip().lower() in ("yes", "si", "sì", "true", "1")
        await self.builder.refresh(interaction)


class ImagesModal(discord.ui.Modal, title="Immagini"):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder
        d = builder.data
        self.immagine = discord.ui.TextInput(label="URL immagine grande", default=d.get("image", ""),
                                             required=False)
        self.thumb = discord.ui.TextInput(label="URL thumbnail (piccola, in alto a dx)",
                                          default=d.get("thumbnail", ""), required=False)
        self.add_item(self.immagine)
        self.add_item(self.thumb)

    async def on_submit(self, interaction):
        self.builder.data["image"] = self.immagine.value
        self.builder.data["thumbnail"] = self.thumb.value
        await self.builder.refresh(interaction)


# ── VIEW DEL BUILDER ──────────────────────────────────────────────────────────
class SendChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📤 Scegli il canale dove inviare...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        ch_id = self.values[0].id
        canale = self.view.guild.get_channel(ch_id) or await self.view.guild.fetch_channel(ch_id)
        await canale.send(embed=costruisci_embed(self.view.data, guild=self.view.guild))
        await interaction.response.send_message(f"✅ Embed inviato in {canale.mention}!", ephemeral=True)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, guild, name, data, author_id):
        super().__init__(timeout=600)
        self.guild = guild
        self.name = name
        self.data = data
        self.author_id = author_id
        self.add_item(SendChannelSelect())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo chi ha aperto l'editor può usarlo.", ephemeral=True)
            return False
        return True

    async def refresh(self, interaction):
        db.save_embed(self.guild.id, self.name, self.data)
        try:
            await interaction.response.edit_message(
                embed=costruisci_embed(self.data, member=interaction.user, guild=self.guild), view=self)
        except discord.HTTPException as e:
            msg = f"⚠️ Errore (controlla gli URL di immagini/icone): {e}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="edit basic information (color / title / description)",
                       style=discord.ButtonStyle.secondary, row=0)
    async def basic(self, interaction, button):
        await interaction.response.send_modal(BasicModal(self))

    @discord.ui.button(label="edit author", style=discord.ButtonStyle.secondary, row=1)
    async def author(self, interaction, button):
        await interaction.response.send_modal(AuthorModal(self))

    @discord.ui.button(label="edit footer", style=discord.ButtonStyle.secondary, row=1)
    async def footer(self, interaction, button):
        await interaction.response.send_modal(FooterModal(self))

    @discord.ui.button(label="edit images", style=discord.ButtonStyle.secondary, row=1)
    async def images(self, interaction, button):
        await interaction.response.send_modal(ImagesModal(self))


# ── SELECT PER /embed edit ────────────────────────────────────────────────────
class EditSelect(discord.ui.Select):
    def __init__(self, names):
        options = [discord.SelectOption(label=n) for n in names[:25]]
        super().__init__(placeholder="Scegli l'embed da modificare...", options=options)

    async def callback(self, interaction: discord.Interaction):
        nome = self.values[0]
        data = db.get_embed(interaction.guild_id, nome) or {}
        view = EmbedBuilderView(interaction.guild, nome, data, interaction.user.id)
        await interaction.response.edit_message(
            content=f"✏️ **Editor embed:** `{nome}`",
            embed=costruisci_embed(data, member=interaction.user, guild=interaction.guild), view=view)


class EditSelectView(discord.ui.View):
    def __init__(self, names, author_id):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(EditSelect(names))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id


# ── COG ─────────────────────────────────────────────────────────────────────
class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    gruppo = app_commands.Group(
        name="embed",
        description="Crea e gestisci embed personalizzati",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @gruppo.command(name="create", description="Crea un nuovo embed e aprilo nell'editor")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction, nome: str):
        if db.get_embed(interaction.guild_id, nome) is not None:
            await interaction.response.send_message(
                f"❌ Esiste già un embed chiamato `{nome}`. Usa `/embed edit`.", ephemeral=True)
            return
        data = {"color": "5865F2"}
        db.save_embed(interaction.guild_id, nome, data)
        view = EmbedBuilderView(interaction.guild, nome, data, interaction.user.id)
        await interaction.response.send_message(
            content=f"✏️ **Editor embed:** `{nome}`",
            embed=costruisci_embed(data, member=interaction.user, guild=interaction.guild),
            view=view, ephemeral=True)

    @gruppo.command(name="edit", description="Modifica un embed esistente (scegli dalla lista)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit(self, interaction: discord.Interaction):
        names = db.list_embeds(interaction.guild_id)
        if not names:
            await interaction.response.send_message(
                "❌ Nessun embed salvato. Creane uno con `/embed create`.", ephemeral=True)
            return
        view = EditSelectView(names, interaction.user.id)
        await interaction.response.send_message("Quale embed vuoi modificare?", view=view, ephemeral=True)

    @gruppo.command(name="list", description="Mostra gli embed salvati")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list(self, interaction: discord.Interaction):
        names = db.list_embeds(interaction.guild_id)
        if not names:
            await interaction.response.send_message("❌ Nessun embed salvato.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Embed salvati", color=0x5865F2,
                              description="\n".join(f"• `{n}`" for n in names))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @gruppo.command(name="delete", description="Elimina un embed salvato")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete(self, interaction: discord.Interaction, nome: str):
        if db.delete_embed(interaction.guild_id, nome):
            await interaction.response.send_message(f"🗑️ Embed `{nome}` eliminato.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Nessun embed chiamato `{nome}`.", ephemeral=True)

    @gruppo.command(name="send", description="Invia un embed salvato in un canale")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def send(self, interaction: discord.Interaction, nome: str, canale: discord.TextChannel = None):
        data = db.get_embed(interaction.guild_id, nome)
        if data is None:
            await interaction.response.send_message(f"❌ Nessun embed chiamato `{nome}`.", ephemeral=True)
            return
        canale = canale or interaction.channel
        await canale.send(embed=costruisci_embed(data, guild=interaction.guild))
        await interaction.response.send_message(f"✅ Embed `{nome}` inviato in {canale.mention}.", ephemeral=True)

    @delete.autocomplete("nome")
    @send.autocomplete("nome")
    async def _nome_ac(self, interaction: discord.Interaction, current: str):
        names = db.list_embeds(interaction.guild_id)
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
