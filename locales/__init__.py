"""Testi dell'interfaccia.

Il bot è in inglese. Le stringhe stanno tutte in `en.py` invece che sparse nei
cog, così sono in un posto solo e facili da rileggere/correggere.

Uso:
    from locales import t
    await ctx.send(t(config, "counting.ruined", user=..., n=22))

`config` non serve più a scegliere la lingua (ce n'è una sola): resta nella
firma perché lo passano già tutte le chiamate, e perché se un giorno servisse
una seconda lingua basta rimetterla qui senza toccare i cog.
"""
from . import en

STRINGS = en.STRINGS


def t(config, key: str, **kwargs) -> str:
    """Testo dell'interfaccia. Se la chiave non esiste la restituisce com'è,
    così è ovvio cosa manca invece di stampare vuoto."""
    testo = STRINGS.get(key)
    if testo is None:
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
    return [r for r in STRINGS.get(key, "").split("\n") if r]
