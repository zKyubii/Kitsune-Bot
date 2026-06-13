import re

# Configurazione di default del sistema livelli (override in config["levels"]).
DEFAULT = {
    "enabled": False,
    "text_enabled": True,
    "voice_enabled": True,
    "xp_min": 15,
    "xp_max": 25,
    "voice_xp": 10,
    "cooldown_text": 60,      # secondi
    "cooldown_voice": 60,     # secondi
    "curve_base": 100,        # XP per passare dal livello 0 al 1
    "curve_increment": 50,    # XP in più per ogni livello successivo
    "level_overrides": {},    # {"5": 1000} → XP per avanzare DAL livello 5
    "levelup_channel": None,
    "levelup_message": "GG {user}, hai raggiunto il **livello {level}**! 🎉",
    "blacklist_roles": [],
    "blacklist_users": [],
    "multipliers": {},        # {"role_id": 2.0}
    "rewards": {},            # {"5": role_id}
    "reward_replace": True,
    "coleave": False,
}


def cfg(config: dict) -> dict:
    """Restituisce la config livelli completa (default + salvato)."""
    return {**DEFAULT, **config.get("levels", {})}


def cost(c: dict, level: int) -> int:
    """XP necessari per avanzare DAL `level` al successivo."""
    ov = c.get("level_overrides", {}).get(str(level))
    if ov is not None:
        try:
            return max(1, int(ov))
        except (ValueError, TypeError):
            pass
    return max(1, int(c["curve_base"] + c["curve_increment"] * level))


def level_info(c: dict, xp: int) -> dict:
    """Calcola livello e progresso da XP totali."""
    level = 0
    total = 0
    while level < 1000:
        nxt = cost(c, level)
        if xp >= total + nxt:
            total += nxt
            level += 1
        else:
            break
    nxt = cost(c, level)
    return {
        "level": level,
        "level_start": total,       # XP totali per ESSERE a questo livello
        "into": xp - total,         # progresso dentro il livello
        "need": nxt,                # XP per il prossimo livello
        "next_total": total + nxt,  # XP totali per il prossimo livello
    }


def level_from_xp(c: dict, xp: int) -> int:
    return level_info(c, xp)["level"]


def get_multiplier(c: dict, role_ids) -> float:
    """Moltiplicatore più alto tra i ruoli del membro (default 1.0)."""
    mult = 1.0
    m = c.get("multipliers", {})
    for rid in role_ids:
        v = m.get(str(rid))
        if v:
            try:
                mult = max(mult, float(v))
            except (ValueError, TypeError):
                pass
    return mult


def is_blacklisted(c: dict, user_id: int, role_ids) -> bool:
    if user_id in c.get("blacklist_users", []):
        return True
    bl = set(c.get("blacklist_roles", []))
    return any(rid in bl for rid in role_ids)


_DUR_RE = re.compile(r"(\d+)\s*([smh]?)", re.IGNORECASE)


def parse_duration(text: str):
    """'30s' / '5m' / '2h' / '90' → secondi (int), oppure None."""
    if not text:
        return None
    m = _DUR_RE.fullmatch(text.strip().lower())
    if not m:
        return None
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def fmt_duration(sec: int) -> str:
    if sec and sec % 3600 == 0:
        return f"{sec // 3600}h"
    if sec and sec % 60 == 0:
        return f"{sec // 60}m"
    return f"{sec}s"
