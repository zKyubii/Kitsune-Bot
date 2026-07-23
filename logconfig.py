from discord import app_commands

# Definizione di tutte le categorie di log e dei rispettivi eventi.
# Struttura: chiave -> (etichetta, {evento: descrizione})
LOG_CATEGORIES = {
    "members": ("logcat.members", {
        "join": "logev.members.join",
        "leave": "logev.members.leave",
        "bot": "logev.members.bot",
        "nickname": "logev.members.nickname",
        "avatar": "logev.members.avatar",
        "role_given": "logev.members.role_given",
        "role_taken": "logev.members.role_taken",
    }),
    "messages": ("logcat.messages", {
        "delete": "logev.messages.delete",
        "bulk_delete": "logev.messages.bulk_delete",
        "edit": "logev.messages.edit",
        "attachment": "logev.messages.attachment",
        "thread": "logev.messages.thread",
        "pin": "logev.messages.pin",
        "reaction": "logev.messages.reaction",
    }),
    "voice": ("logcat.voice", {
        "join_leave": "logev.voice.join_leave",
        "mute_deaf": "logev.voice.mute_deaf",
        "stream_video": "logev.voice.stream_video",
    }),
    "channels": ("logcat.channels", {
        "create": "logev.channels.create",
        "delete": "logev.channels.delete",
        "update": "logev.channels.update",
        "permissions": "logev.channels.permissions",
        "webhook": "logev.channels.webhook",
    }),
    "roles": ("logcat.roles", {
        "create": "logev.roles.create",
        "delete": "logev.roles.delete",
        "update": "logev.roles.update",
    }),
    "server": ("logcat.server", {
        "update": "logev.server.update",
        "boost": "logev.server.boost",
    }),
    "actions": ("logcat.actions", {
        "invite_create": "logev.actions.invite_create",
        "invite_delete": "logev.actions.invite_delete",
        "emoji": "logev.actions.emoji",
        "event": "logev.actions.event",
    }),
    "modlogs": ("logcat.modlogs", {
        "ban": "logev.modlogs.ban",
        "kick": "logev.modlogs.kick",
        "timeout": "logev.modlogs.timeout",
        "lock": "logev.modlogs.lock",
    }),
}

# Funzioni del bot attivabili/disattivabili dalla dashboard
FEATURES = {
    "minigames": "feat.minigames",
    "fun": "feat.fun",
    "confession": "feat.confession",
    "quote": "feat.quote",
    "partnership": "feat.partnership",
    "automsg": "feat.automsg",
    "autoreact": "feat.autoreact",
    "profile": "feat.profile",
    "counting": "feat.counting",
    "poll": "feat.poll",
}


# ── PROFILO UTENTE ──────────────────────────────────────────────────────────
# Config per-server salvata in log_config["profile"]:
#   privacy_bypass_roles: [role_id]                ruoli che ignorano la privacy altrui
#   private_voices:       {channel_id: user_id}    vocali assegnate manualmente
#   custom_react:         {"allowed_roles": [role_id], "max": int}
#   primary_roles:        {user_id: role_id}        ruolo "primario" mostrato
def profile_cfg(config: dict) -> dict:
    return config.get("profile", {})


def privacy_bypass_roles(config: dict) -> list:
    return profile_cfg(config).get("privacy_bypass_roles", [])


def private_voice_of(config: dict, user_id: int):
    """Id del canale vocale assegnato all'utente, se esiste."""
    for cid, uid in profile_cfg(config).get("private_voices", {}).items():
        if uid == user_id:
            return int(cid)
    return None


def custom_react_allowed(config: dict, member) -> bool:
    """True se il membro ha uno dei ruoli abilitati alle custom reactions."""
    allowed = profile_cfg(config).get("custom_react", {}).get("allowed_roles", [])
    if not allowed:
        return False
    return any(r.id in allowed for r in getattr(member, "roles", []))


def custom_react_max(config: dict) -> int:
    return profile_cfg(config).get("custom_react", {}).get("max", 3)


def primary_role_of(config: dict, user_id: int):
    rid = profile_cfg(config).get("primary_roles", {}).get(str(user_id))
    return int(rid) if rid else None


def role_categories(config: dict) -> dict:
    """{cat_id: {name, emoji, single, roles:[role_id]}} — categorie di self-role."""
    return profile_cfg(config).get("role_categories", {})


# ── CUSTOM REACTIONS = regola "mention" dell'autoreact (dato condiviso) ──────
def mention_rule_for(config: dict, user_id: int):
    """La regola autoreact di tipo 'mention' che scatta quando l'utente è taggato."""
    for r in config.get("autoreact", {}).get("rules", []):
        if r.get("type") == "mention" and str(r.get("trigger")) == str(user_id):
            return r
    return None


def ensure_mention_rule(config: dict, user_id: int, source: str = None) -> dict:
    """Restituisce la regola mention dell'utente, creandola vuota se non esiste.

    `source="profile"` marca la regola come creata dal sistema profilo (custom
    reactions): serve per distinguerla dalle mention create a mano dall'admin
    nell'Autoreact, così possiamo rimuoverla quando l'utente perde il ruolo.
    """
    rules = config.setdefault("autoreact", {}).setdefault("rules", [])
    existing = mention_rule_for(config, user_id)
    if existing is not None:
        if source:
            existing["source"] = source
        return existing
    new_id = max((r.get("id", 0) for r in rules if isinstance(r.get("id"), int)), default=0) + 1
    rule = {"id": new_id, "type": "mention", "trigger": str(user_id),
            "mode": "contains", "emojis": []}
    if source:
        rule["source"] = source
    rules.append(rule)
    return rule


def remove_mention_rule(config: dict, user_id: int):
    rules = config.get("autoreact", {}).get("rules", [])
    config.setdefault("autoreact", {})["rules"] = [
        r for r in rules
        if not (r.get("type") == "mention" and str(r.get("trigger")) == str(user_id))
    ]


def remove_profile_mention_rule(config: dict, user_id: int) -> bool:
    """Rimuove la mention-rule dell'utente SOLO se è una custom reaction del
    profilo (source='profile'). Lascia intatte le mention create dall'admin.
    Ritorna True se ha rimosso qualcosa."""
    r = mention_rule_for(config, user_id)
    if r is not None and r.get("source") == "profile":
        remove_mention_rule(config, user_id)
        return True
    return False


# ── ANTISPAM ──────────────────────────────────────────────────────────────────
SPAM_CATEGORIES = {
    "spam": "spam.spam",
    "selfbot": "spam.selfbot",
    "mentions": "spam.mentions",
    "links": "spam.links",
    "external": "spam.external",
    "duplicates": "spam.duplicates",
    "important": "spam.important",
}

SANCTIONS = {
    "none": "sanction.none",
    "warn": "sanction.warn",
    "timeout": "sanction.timeout",
    "kick": "sanction.kick",
    "softban": "sanction.softban",
    "ban": "sanction.ban",
}

# Configurazione di default per ogni categoria
DEFAULT_SPAM = {
    "spam": {"enabled": True, "sanction": "timeout", "seconds": 600},
    "selfbot": {"enabled": True, "sanction": "ban", "seconds": 0},
    "mentions": {"enabled": True, "sanction": "timeout", "seconds": 600},
    "links": {"enabled": True, "sanction": "timeout", "seconds": 600},
    "external": {"enabled": True, "sanction": "timeout", "seconds": 300},
    "duplicates": {"enabled": True, "sanction": "timeout", "seconds": 600},
    "important": {"enabled": True, "sanction": "kick", "seconds": 0},
}


def categoria_cfg(config: dict, key: str) -> dict:
    salvato = config.get("antispam", {}).get("categories", {}).get(key, {})
    return {**DEFAULT_SPAM[key], **salvato}


def antispam_attivo(config: dict) -> bool:
    return config.get("antispam", {}).get("enabled", False)


def is_enabled(config: dict, category: str, event: str) -> bool:
    cat = config.get("logs", {}).get(category)
    if not cat or not cat.get("channel"):
        return False
    return cat.get("events", {}).get(event, False)


def get_channel_id(config: dict, category: str):
    return config.get("logs", {}).get(category, {}).get("channel")


def feature_enabled(config: dict, feature: str) -> bool:
    # Di default tutte le funzioni sono attive
    return config.get("features", {}).get(feature, True)


class FeatureDisabled(app_commands.CheckFailure):
    """Sollevata quando si usa un comando di una funzione disattivata."""
    pass


def feature_check(feature: str):
    """Decoratore: blocca il comando se la funzione è disattivata sul server."""
    import database as db

    async def predicate(interaction):
        config = db.get_log_config(interaction.guild_id)
        if not feature_enabled(config, feature):
            raise FeatureDisabled()
        return True

    return app_commands.check(predicate)
