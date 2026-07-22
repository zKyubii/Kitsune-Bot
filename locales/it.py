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

    # ── MODERAZIONE ─────────────────────────────────────────────────────────
    "mod.self_target": "❌ Non puoi usare questo comando su te stesso.",
    "mod.owner_target": "❌ Non puoi moderare il proprietario del server.",
    "mod.higher_role": "❌ Non puoi moderare un utente con ruolo uguale o superiore al tuo.",
    "mod.bot_role_low": "❌ Il mio ruolo è troppo basso: spostalo sopra quello dell'utente da moderare.",
    "mod.no_role_perm": "⛔ Non hai un ruolo autorizzato per questo comando.",
    "mod.missing_perm": "⛔ Non hai il permesso necessario per questo comando: `{perms}`",
    "mod.bot_missing_perm": "⚠️ Mi manca il permesso necessario: `{perms}`",
    "mod.generic_error": "❌ Si è verificato un errore: {error}",
    "mod.error": "❌ Errore: {error}",
    "mod.bad_duration": "❌ Formato durata non valido. Usa es: `30s`, `10m`, `2h`, `7d`",
    "mod.timeout_max": "❌ Il timeout massimo consentito da Discord è **28 giorni** (`28d`).",
    "mod.bad_id": "❌ ID non valido.",
    "mod.user_not_found": "❌ Utente non trovato.",
    "mod.user_not_banned": "❌ Utente non trovato o non bannato.",
    "mod.slowmode_need_value": "❌ Scegli un preset oppure inserisci un valore personalizzato in secondi.",
    "mod.slowmode_off": "✅ Slowmode disattivato.",
    "mod.slowmode_set": "🐢 Slowmode impostato a **{value}**.",
    "mod.no_bans": "✅ Non ci sono utenti bannati in questo server.",
    "mod.cleared": "🗑️ Eliminati **{n}** messaggi.",
    "mod.warn_self": "❌ Non puoi avvisare te stesso.",
    "mod.warn_bot": "❌ Non puoi avvisare un bot.",
    "mod.no_warns": "✅ **{user}** non ha warn.",
    "mod.had_no_warns": "✅ **{user}** non aveva warn.",
    "mod.warn_removed": "✅ Warn **#{id}** rimosso.",
    "mod.warn_not_found": "❌ Nessun warn con ID #{id}.",
    "mod.warn_dm_title": "⚠️ Sei stato avvisato in {guild}",
    "mod.warns_title": "⚠️ Warn di {user}",
    "mod.auto_kick": "👢 Kick automatico",
    "mod.auto_ban": "🔨 Ban automatico",
    "mod.auto_failed": "⚠️ Azione automatica non riuscita (permessi o ruolo troppo alto)",
    "mod.jail_not_configured": "❌ Il sistema Jail non è configurato. "
                               "Vai su `/dashboard` → 🛡️ Moderazione → 🔒 Jail → **Setup**.",
    "mod.no_jailed": "✅ Nessun utente è attualmente in jail.",
    "mod.only_author": "❌ Solo chi ha usato il comando può sfogliare.",
    "mod.already_jailed": "❌ **{user}** è già in jail.",
    "mod.not_jailed": "❌ **{user}** non è in jail.",
    # embed di moderazione
    "mod.embed_reason": "📋 **Reason:**",
    "mod.embed_moderator": "👤 **Moderator:**",
    "mod.embed_duration": "🕐 **Duration:**",
    "mod.embed_purged": "🧹 **Purged:**",
    "mod.embed_purged_value": "ultimi {days} giorni",
    "mod.embed_proof": "🔗 Proof",
    "mod.embed_attachment": "[Allegato]({url})",

    # ── AVATAR / BANNER ─────────────────────────────────────────────────────
    "avatar.no_banner": "❌ {user} non ha un banner.",
    "avatar.no_profile_banner": "❌ {user} non ha un banner sul profilo.",

    # ── QUOTE ───────────────────────────────────────────────────────────────
    "quote.only_author": "❌ Solo chi ha creato la quote può modificarla.",
    "quote.disabled": "🚫 La funzione Quote è disattivata su questo server.",
    "quote.no_text": "❌ Questo messaggio non ha testo da citare.",
    "quote.no_text_short": "❌ Quel messaggio non ha testo da citare.",
    "quote.created": "✅ Quote creata in {channel}! Personalizzala con i bottoni sul messaggio.",
    "quote.font": "🎨 Seleziona Font",
    "quote.background": "Sfondo",
    "quote.bold": "Grassetto",

    # ── CONFESSION ──────────────────────────────────────────────────────────
    "conf.modal_title": "Confessione anonima",
    "conf.modal_label": "La tua confessione",
    "conf.placeholder": "Scrivi qui... resterà anonima 🤫",
    "conf.disabled_short": "🚫 Le confessioni sono disattivate.",
    "conf.disabled": "🚫 Le confessioni sono disattivate su questo server.",
    "conf.not_configured": "❌ Le confessioni non sono configurate.",
    "conf.not_configured_admin": "❌ Le confessioni non sono configurate. Un admin deve "
                                 "impostarle da `/dashboard` → 🔧 Funzioni → Confession.",
    "conf.channel_gone": "❌ Il canale delle confessioni non esiste più.",
    "conf.no_perm": "⛔ Non hai il permesso necessario per questo comando.",
    "conf.published": "✅ La tua confessione **#{n}** è stata pubblicata in {channel}!",

    # ── RUOLI ───────────────────────────────────────────────────────────────
    "roles.everyone": "❌ Non puoi assegnare il ruolo @everyone.",
    "roles.managed": "❌ Questo ruolo è gestito da un'integrazione e non può essere assegnato manualmente.",
    "roles.bot_too_low": "❌ Il mio ruolo è troppo basso: spostalo sopra il ruolo da assegnare.",
    "roles.higher": "❌ Non puoi gestire un ruolo uguale o superiore al tuo.",
    "roles.need_perm": "⛔ Ti serve il permesso **Gestisci ruoli**.",
    "roles.already_has": "❌ {user} ha già {role}.",
    "roles.doesnt_have": "❌ {user} non ha {role}.",
    "roles.added": "✅ {role} aggiunto a {user}.",
    "roles.removed": "✅ {role} rimosso a {user}.",
    "roles.mass_done": "✅ {role} {verb} **{count}** {what}.",

    # ── PARTNERSHIP ─────────────────────────────────────────────────────────
    "partner.channel_gone": "❌ Il canale delle partnership non è più configurato.",
    "partner.no_write_perm": "❌ Non ho i permessi per scrivere nel canale delle partnership.",
    "partner.send_error": "❌ Errore nell'invio: {error}",
    "partner.published": "✅ Partnership pubblicata in {channel}!",
    "partner.disabled": "❌ La funzione **Partnership** è disattivata su questo server.",
    "partner.no_role": "❌ Non hai un ruolo autorizzato a fare partnership.",

    # ── COUNTING: messaggi in chat ──────────────────────────────────────────
    "counting.deleted": "⚠️ {user} ha cancellato il suo numero: ```{n}```"
                        "Il prossimo numero è **{next}**.",
    "counting.ruined": "💥 {user} **HA ROVINATO TUTTO A {n}!!**\n"
                       "Il prossimo numero è **1**.\n"
                       "{reason}\n{record}",
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
