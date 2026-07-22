"""Testi in italiano. Le chiavi sono `sezione.nome`."""

STRINGS = {
    # ── GENERICI (riusati ovunque) ──────────────────────────────────────────
    "common.enabled": "🟢 Attiva",
    "common.disabled": "🔴 Disattivata",
    "common.not_set": "❌ non impostato",
    "common.none": "*Nessuno*",
    "common.back": "Indietro",
    "common.activate": "Attiva",
    "common.deactivate": "Disattiva",
    "common.state": "Stato",
    "common.channel": "📢 Canale",

    # ── DASHBOARD: lingua ───────────────────────────────────────────────────
    "lang.placeholder": "🌍 Lingua del bot...",
    "lang.field": "🌍 Lingua",

    # ── COUNTING: messaggi in chat ──────────────────────────────────────────
    "counting.deleted": "⚠️ {user} ha cancellato il suo numero: ```{n}```"
                        "Il prossimo numero è **{next}**.",
    "counting.ruined": "💥 {user} **HA ROVINATO TUTTO A {n}!!** "
                       "Il prossimo numero è **1**. {reason}\n{record}",
    "counting.reason_double": "Non puoi contare due volte di fila.",
    "counting.reason_wrong": "Numero sbagliato: toccava **{expected}**.",
    "counting.record_new": "🏆 **Nuovo record: {record}!**",
    "counting.record_current": "🏆 Record del server: **{record}**",

    # ── COUNTING: dashboard ─────────────────────────────────────────────────
    "counting.title": "🔢 Counting",
    "counting.desc": "Si conta a turno nel canale scelto: **non si può contare due volte di fila**.\n"
                     "I messaggi che non sono numeri vengono ignorati.",
    "counting.channel_placeholder": "🔢 Canale del counting...",
    "counting.on_fail": "Se sbagliano",
    "counting.on_fail_reset": "il conteggio riparte da 1",
    "counting.on_fail_delete": "il messaggio sbagliato viene cancellato",
    "counting.btn_reset_on": "Se sbagliano: riparte da 1",
    "counting.btn_reset_off": "Se sbagliano: cancella e basta",
    "counting.btn_react_on": "Reazione ✅ attiva",
    "counting.btn_react_off": "Reazione ✅ spenta",
    "counting.btn_clear": "Azzera conteggio",
    "counting.btn_milestones": "Traguardi",
    "counting.current": "Numero attuale",
    "counting.current_value": "**{n}** (prossimo: {next})",
    "counting.record": "🏆 Record",
    "counting.react_field": "Reazione ✅",
    "counting.react_on": "attiva",
    "counting.react_off": "spenta",
    "counting.milestones": "🏁 Traguardi",
    "counting.milestones_none": "nessuno",
    "counting.milestone_entry": "{emoji} a {n}",
    "counting.footer": "Se qualcuno cancella il suo numero, il bot avvisa qual è il prossimo.",
    "counting.modal_title": "Traguardi",
    "counting.modal_label": "Numero: emoji (separati da virgola)",
}
