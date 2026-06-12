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


# ── SELF-ROLE: componenti (menu a tendina / pulsanti che assegnano ruoli) ─────
_STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}
_STYLE_LABELS = {"primary": "Blu", "secondary": "Grigio", "success": "Verde", "danger": "Rosso"}
_STYLE_FROM_IT = {"blu": "primary", "grigio": "secondary", "verde": "success", "rosso": "danger"}


def _parse_emoji(raw):
    """Converte una stringa emoji (unicode o <:nome:id>) in PartialEmoji, o None."""
    if not raw:
        return None
    try:
        return discord.PartialEmoji.from_str(str(raw).strip())
    except Exception:
        return None


def build_role_view(data: dict, guild) -> discord.ui.View | None:
    """Costruisce la view (menu + pulsanti) da allegare al messaggio pubblicato."""
    comps = data.get("components") or []
    if not comps:
        return None
    view = discord.ui.View(timeout=None)
    row = 0
    for i, comp in enumerate(comps):
        if row > 4:
            break
        if comp.get("type") == "select":
            options = []
            for o in comp.get("options", []):
                role = guild.get_role(o["role"]) if guild else None
                label = o.get("label") or (role.name if role else f"Ruolo {o['role']}")
                options.append(discord.SelectOption(
                    label=label[:100], value=str(o["role"]),
                    description=(o.get("description") or None),
                    emoji=_parse_emoji(o.get("emoji"))))
            if not options:
                continue
            single = comp.get("single")
            view.add_item(discord.ui.Select(
                placeholder=comp.get("placeholder") or "Seleziona un ruolo…",
                min_values=0, max_values=1 if single else len(options),
                options=options, custom_id=f"erole:sel:{i}", row=row))
            row += 1
        elif comp.get("type") == "buttons":
            btns = comp.get("buttons", [])
            if not btns:
                continue
            for b in btns[:5]:
                role = guild.get_role(b["role"]) if guild else None
                label = b.get("label") or (role.name if role else None)
                emoji = _parse_emoji(b.get("emoji"))
                if not label and not emoji:
                    label = f"Ruolo {b['role']}"
                view.add_item(discord.ui.Button(
                    label=label, emoji=emoji,
                    style=_STYLE_MAP.get(b.get("style", "secondary"), discord.ButtonStyle.secondary),
                    custom_id=f"erole:btn:{b['role']}", row=row))
            row += 1
    return view if view.children else None


async def _apply_select(interaction, custom_id, values):
    """Aggiunge i ruoli selezionati e toglie quelli deselezionati (solo del menu)."""
    guild, member = interaction.guild, interaction.user
    managed = []
    for arow in interaction.message.components:
        for comp in arow.children:
            if getattr(comp, "custom_id", None) == custom_id:
                managed = [int(o.value) for o in getattr(comp, "options", [])]
    selected = {int(v) for v in values}
    add, remove = [], []
    for rid in managed:
        role = guild.get_role(rid)
        if not role or role.managed or role >= guild.me.top_role:
            continue
        if rid in selected and role not in member.roles:
            add.append(role)
        elif rid not in selected and role in member.roles:
            remove.append(role)
    try:
        if add:
            await member.add_roles(*add, reason="Self-role menu")
        if remove:
            await member.remove_roles(*remove, reason="Self-role menu")
    except discord.Forbidden:
        return await interaction.response.send_message(
            "❌ Non riesco a gestire questi ruoli: sposta il mio ruolo più in alto nella gerarchia.",
            ephemeral=True)
    parts = []
    if add:
        parts.append("➕ " + " ".join(r.mention for r in add))
    if remove:
        parts.append("➖ " + " ".join(r.mention for r in remove))
    await interaction.response.send_message("\n".join(parts) or "Nessuna modifica.", ephemeral=True)


async def _apply_button(interaction, role_id):
    """Clic su pulsante: aggiunge il ruolo se non c'è, lo toglie se c'è."""
    guild, member = interaction.guild, interaction.user
    role = guild.get_role(role_id)
    if not role:
        return await interaction.response.send_message("❌ Ruolo non trovato.", ephemeral=True)
    if role.managed or role >= guild.me.top_role:
        return await interaction.response.send_message(
            "❌ Non posso gestire questo ruolo (controlla la gerarchia).", ephemeral=True)
    try:
        if role in member.roles:
            await member.remove_roles(role, reason="Self-role button")
            await interaction.response.send_message(f"➖ Rimosso {role.mention}", ephemeral=True)
        else:
            await member.add_roles(role, reason="Self-role button")
            await interaction.response.send_message(f"➕ Aggiunto {role.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)


class RoleMenuSelect(discord.ui.DynamicItem[discord.ui.Select],
                     template=r"erole:sel:(?P<idx>\d+)"):
    """Gestore persistente per i menu a tendina dei ruoli (anche dopo riavvio)."""
    def __init__(self, idx: int):
        super().__init__(discord.ui.Select(
            custom_id=f"erole:sel:{idx}", min_values=0, max_values=1,
            options=[discord.SelectOption(label="placeholder")]))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["idx"]))

    async def callback(self, interaction):
        await _apply_select(interaction, self.item.custom_id, interaction.data.get("values", []))


class RoleMenuButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"erole:btn:(?P<rid>\d+)"):
    """Gestore persistente per i pulsanti dei ruoli (anche dopo riavvio)."""
    def __init__(self, role_id: int):
        super().__init__(discord.ui.Button(custom_id=f"erole:btn:{role_id}"))
        self.role_id = role_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["rid"]))

    async def callback(self, interaction):
        await _apply_button(interaction, self.role_id)


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


# ── SOTTO-EDITOR: costruzione menu / pulsanti ruolo ───────────────────────────
class OptionModal(discord.ui.Modal, title="Opzione del menu"):
    def __init__(self, menu_view, role):
        super().__init__()
        self.menu_view = menu_view
        self.role = role
        self.etichetta = discord.ui.TextInput(label="Etichetta", default=role.name, max_length=100)
        self.emoji = discord.ui.TextInput(label="Emoji (opzionale)", required=False, max_length=100,
                                          placeholder="😀  oppure  <:nome:id>")
        self.descrizione = discord.ui.TextInput(label="Descrizione (opzionale)", required=False, max_length=100)
        self.add_item(self.etichetta)
        self.add_item(self.emoji)
        self.add_item(self.descrizione)

    async def on_submit(self, interaction):
        self.menu_view.options.append({
            "role": self.role.id,
            "label": self.etichetta.value,
            "emoji": self.emoji.value,
            "description": self.descrizione.value,
        })
        await interaction.response.defer()
        await self.menu_view.message.edit(content=self.menu_view.render(), view=self.menu_view)


class MenuSettingsModal(discord.ui.Modal, title="Impostazioni menu"):
    def __init__(self, menu_view):
        super().__init__()
        self.menu_view = menu_view
        self.placeholder = discord.ui.TextInput(
            label="Testo segnaposto", required=False, max_length=150,
            default=menu_view.placeholder, placeholder="Seleziona un ruolo…")
        self.single = discord.ui.TextInput(
            label="Scelta singola? (si/no)", required=False, max_length=3,
            default="si" if menu_view.single else "no")
        self.add_item(self.placeholder)
        self.add_item(self.single)

    async def on_submit(self, interaction):
        self.menu_view.placeholder = self.placeholder.value
        self.menu_view.single = self.single.value.strip().lower() in ("si", "sì", "yes", "y", "1")
        await interaction.response.defer()
        await self.menu_view.message.edit(content=self.menu_view.render(), view=self.menu_view)


class MenuRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="➕ Scegli un ruolo da aggiungere al menu…",
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction):
        if len(self.view.options) >= 25:
            return await interaction.response.send_message("❌ Massimo 25 opzioni per menu.", ephemeral=True)
        await interaction.response.send_modal(OptionModal(self.view, self.values[0]))


class MenuBuilderView(discord.ui.View):
    def __init__(self, builder):
        super().__init__(timeout=600)
        self.builder = builder
        self.options = []
        self.placeholder = ""
        self.single = False
        self.message = None
        self.add_item(MenuRoleSelect())

    async def interaction_check(self, interaction):
        return interaction.user.id == self.builder.author_id

    def render(self):
        righe = [f"🎭 **Nuovo menu a tendina** — {len(self.options)} opzioni"]
        for o in self.options:
            em = (o["emoji"] + " ") if o.get("emoji") else ""
            righe.append(f"• {em}{o['label']} → <@&{o['role']}>")
        modo = "scelta singola" if self.single else "scelta multipla"
        righe.append(f"\n_Segnaposto: {self.placeholder or 'Seleziona un ruolo…'} · {modo}_")
        righe.append("Aggiungi le opzioni col menu qui sotto, poi premi **Salva menu**.")
        return "\n".join(righe)

    @discord.ui.button(label="⚙️ Impostazioni", style=discord.ButtonStyle.secondary, row=1)
    async def settings(self, interaction, button):
        await interaction.response.send_modal(MenuSettingsModal(self))

    @discord.ui.button(label="✅ Salva menu", style=discord.ButtonStyle.success, row=1)
    async def save(self, interaction, button):
        if not self.options:
            return await interaction.response.send_message("❌ Aggiungi almeno un'opzione.", ephemeral=True)
        self.builder.data.setdefault("components", []).append({
            "type": "select",
            "placeholder": self.placeholder,
            "single": self.single,
            "options": self.options,
        })
        db.save_embed(self.builder.guild.id, self.builder.name, self.builder.data)
        await self.builder.update_message()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ Menu salvato e aggiunto all'embed!", view=self)
        self.stop()


class ButtonOptionModal(discord.ui.Modal, title="Pulsante ruolo"):
    def __init__(self, btn_view, role):
        super().__init__()
        self.btn_view = btn_view
        self.role = role
        self.etichetta = discord.ui.TextInput(label="Etichetta", default=role.name, required=False, max_length=80)
        self.emoji = discord.ui.TextInput(label="Emoji (opzionale)", required=False, max_length=100,
                                          placeholder="😀  oppure  <:nome:id>")
        self.colore = discord.ui.TextInput(label="Colore: blu / grigio / verde / rosso", required=False,
                                           max_length=10, default="grigio")
        self.add_item(self.etichetta)
        self.add_item(self.emoji)
        self.add_item(self.colore)

    async def on_submit(self, interaction):
        self.btn_view.buttons.append({
            "role": self.role.id,
            "label": self.etichetta.value,
            "emoji": self.emoji.value,
            "style": _STYLE_FROM_IT.get(self.colore.value.strip().lower(), "secondary"),
        })
        await interaction.response.defer()
        await self.btn_view.message.edit(content=self.btn_view.render(), view=self.btn_view)


class ButtonRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="➕ Scegli un ruolo da aggiungere come pulsante…",
                         min_values=1, max_values=1, row=0)

    async def callback(self, interaction):
        if len(self.view.buttons) >= 5:
            return await interaction.response.send_message("❌ Massimo 5 pulsanti per gruppo.", ephemeral=True)
        await interaction.response.send_modal(ButtonOptionModal(self.view, self.values[0]))


class ButtonsBuilderView(discord.ui.View):
    def __init__(self, builder):
        super().__init__(timeout=600)
        self.builder = builder
        self.buttons = []
        self.message = None
        self.add_item(ButtonRoleSelect())

    async def interaction_check(self, interaction):
        return interaction.user.id == self.builder.author_id

    def render(self):
        righe = [f"🔘 **Nuovi pulsanti** — {len(self.buttons)}/5"]
        for b in self.buttons:
            em = (b["emoji"] + " ") if b.get("emoji") else ""
            righe.append(f"• {em}{b.get('label') or ''} → <@&{b['role']}> ({_STYLE_LABELS.get(b['style'])})")
        righe.append("Aggiungi i pulsanti col menu qui sotto, poi premi **Salva pulsanti**.")
        return "\n".join(righe)

    @discord.ui.button(label="✅ Salva pulsanti", style=discord.ButtonStyle.success, row=1)
    async def save(self, interaction, button):
        if not self.buttons:
            return await interaction.response.send_message("❌ Aggiungi almeno un pulsante.", ephemeral=True)
        self.builder.data.setdefault("components", []).append({"type": "buttons", "buttons": self.buttons})
        db.save_embed(self.builder.guild.id, self.builder.name, self.builder.data)
        await self.builder.update_message()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ Pulsanti salvati e aggiunti all'embed!", view=self)
        self.stop()


class ComponentRemoveSelect(discord.ui.Select):
    def __init__(self, builder):
        self.builder = builder
        options = []
        for i, c in enumerate(builder.data.get("components", [])):
            if c.get("type") == "select":
                options.append(discord.SelectOption(
                    label=f"Menu a tendina • {len(c.get('options', []))} ruoli", value=str(i), emoji="🎭"))
            else:
                options.append(discord.SelectOption(
                    label=f"Pulsanti • {len(c.get('buttons', []))} ruoli", value=str(i), emoji="🔘"))
        super().__init__(placeholder="Scegli un componente da rimuovere…",
                         options=options or [discord.SelectOption(label="—")], min_values=1, max_values=1)

    async def callback(self, interaction):
        idx = int(self.values[0])
        comps = self.builder.data.get("components", [])
        if 0 <= idx < len(comps):
            comps.pop(idx)
            db.save_embed(self.builder.guild.id, self.builder.name, self.builder.data)
            await self.builder.update_message()
        await interaction.response.edit_message(content="🗑️ Componente rimosso.", view=None)


class ComponentsManagerView(discord.ui.View):
    def __init__(self, builder):
        super().__init__(timeout=300)
        self.builder = builder
        self.add_item(ComponentRemoveSelect(builder))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.builder.author_id


# ── VIEW DEL BUILDER ──────────────────────────────────────────────────────────
class SendChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📤 Scegli il canale dove inviare...",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        ch_id = self.values[0].id
        canale = self.view.guild.get_channel(ch_id) or await self.view.guild.fetch_channel(ch_id)
        await canale.send(embed=costruisci_embed(self.view.data, guild=self.view.guild),
                          view=build_role_view(self.view.data, self.view.guild))
        await interaction.response.send_message(f"✅ Embed inviato in {canale.mention}!", ephemeral=True)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, guild, name, data, author_id):
        super().__init__(timeout=600)
        self.guild = guild
        self.name = name
        self.data = data
        self.author_id = author_id
        self.message = None
        self.add_item(SendChannelSelect())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo chi ha aperto l'editor può usarlo.", ephemeral=True)
            return False
        return True

    def _summary(self):
        comps = self.data.get("components", [])
        if not comps:
            return ""
        parts = []
        for c in comps:
            if c.get("type") == "select":
                parts.append(f"🎭 Menu ({len(c.get('options', []))} ruoli)")
            else:
                parts.append(f"🔘 Pulsanti ({len(c.get('buttons', []))} ruoli)")
        return "\n**Componenti ruolo:** " + " · ".join(parts)

    def _content(self):
        return f"✏️ **Editor embed:** `{self.name}`" + self._summary()

    async def update_message(self):
        """Aggiorna il messaggio dell'editor (usato dai sotto-editor dei componenti)."""
        if self.message:
            try:
                await self.message.edit(
                    content=self._content(),
                    embed=costruisci_embed(self.data, guild=self.guild), view=self)
            except discord.HTTPException:
                pass

    async def refresh(self, interaction):
        db.save_embed(self.guild.id, self.name, self.data)
        try:
            await interaction.response.edit_message(
                content=self._content(),
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

    @discord.ui.button(label="🎭 Menu ruoli", style=discord.ButtonStyle.primary, row=3)
    async def add_menu(self, interaction, button):
        mv = MenuBuilderView(self)
        await interaction.response.send_message(content=mv.render(), view=mv, ephemeral=True)
        mv.message = await interaction.original_response()

    @discord.ui.button(label="🔘 Pulsanti ruoli", style=discord.ButtonStyle.primary, row=3)
    async def add_buttons(self, interaction, button):
        bv = ButtonsBuilderView(self)
        await interaction.response.send_message(content=bv.render(), view=bv, ephemeral=True)
        bv.message = await interaction.original_response()

    @discord.ui.button(label="🗑️ Componenti", style=discord.ButtonStyle.danger, row=3)
    async def manage_components(self, interaction, button):
        if not self.data.get("components"):
            return await interaction.response.send_message("Nessun componente da rimuovere.", ephemeral=True)
        await interaction.response.send_message(
            "Scegli il componente da rimuovere:", view=ComponentsManagerView(self), ephemeral=True)


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
            content=view._content(),
            embed=costruisci_embed(data, member=interaction.user, guild=interaction.guild), view=view)
        view.message = interaction.message


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

    async def cog_load(self):
        # Registra i gestori persistenti di menu/pulsanti ruolo (validi anche dopo riavvio).
        self.bot.add_dynamic_items(RoleMenuSelect, RoleMenuButton)

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
            content=view._content(),
            embed=costruisci_embed(data, member=interaction.user, guild=interaction.guild),
            view=view, ephemeral=True)
        view.message = await interaction.original_response()

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
        await canale.send(embed=costruisci_embed(data, guild=interaction.guild),
                          view=build_role_view(data, interaction.guild))
        await interaction.response.send_message(f"✅ Embed `{nome}` inviato in {canale.mention}.", ephemeral=True)

    @delete.autocomplete("nome")
    @send.autocomplete("nome")
    async def _nome_ac(self, interaction: discord.Interaction, current: str):
        names = db.list_embeds(interaction.guild_id)
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
