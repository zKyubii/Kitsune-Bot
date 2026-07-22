"""Sistema di traduzione (i18n).

La lingua è un'impostazione PER-SERVER salvata in `log_config["lang"]`, quindi
lo stesso bot parla italiano su un server e inglese su un altro.

Uso:
    from locales import t
    await ctx.send(t(config, "counting.ruined", user=..., n=22))

Se una chiave non è ancora tradotta nella lingua richiesta si ripiega sulle
altre: una migrazione a metà non rompe mai un messaggio.
"""
from . import it, en

# Lingua usata quando un server non ne ha scelta una.
# Quando il bot diventerà pubblico basta cambiare questa riga in "en".
DEFAULT_LANG = "it"

LANGS = {"it": it.STRINGS, "en": en.STRINGS}
LANG_NAMES = {"it": "🇮🇹 Italiano", "en": "🇬🇧 English"}


def lang_of(config: dict) -> str:
    return (config or {}).get("lang", DEFAULT_LANG)


def t(config, key: str, **kwargs) -> str:
    """Testo localizzato.

    `config` è il log_config del server (oppure direttamente il codice lingua).
    """
    lingua = config if isinstance(config, str) else lang_of(config)

    testo = LANGS.get(lingua, {}).get(key)
    if testo is None:                                   # non tradotta: default
        testo = LANGS[DEFAULT_LANG].get(key)
    if testo is None:                                   # né lì: qualsiasi lingua
        for altra in LANGS.values():
            if key in altra:
                testo = altra[key]
                break
    if testo is None:                                   # chiave inesistente
        return key

    try:
        return testo.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return testo


def tlist(config, key: str) -> list:
    """Righe di una chiave multi-valore (es. frasi random), NON formattate.

    Serve quando il testo contiene segnaposto da riempire dopo la scelta
    casuale (come `{a}` e `{b}` nelle frasi di /ship).
    """
    lingua = config if isinstance(config, str) else lang_of(config)
    testo = LANGS.get(lingua, {}).get(key) or LANGS[DEFAULT_LANG].get(key, "")
    return [r for r in testo.split("\n") if r]
