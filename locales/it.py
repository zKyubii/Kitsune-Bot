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
    "dash.log_cat_placeholder": "📋 Scegli una categoria di log...",
    "dash.feature_placeholder": "Scegli una funzione da configurare...",
    "lang.placeholder": "🌍 Lingua del bot...",
    "lang.field": "🌍 Lingua",


    # ── ETICHETTE: funzioni ─────────────────────────────────────────────────
    "feat.minigames": "🎮 Minigiochi",
    "feat.fun": "💘 Fun (ship)",
    "feat.confession": "🤫 Confession",
    "feat.quote": "💬 Quote",
    "feat.partnership": "🤝 Partnership",
    "feat.automsg": "📨 Auto Message",
    "feat.autoreact": "⭐ Reaction automatiche",
    "feat.profile": "👤 Profilo utente",
    "feat.counting": "🔢 Counting",

    # ── ETICHETTE: categorie di log ─────────────────────────────────────────
    "logcat.members": "👥 Members",
    "logcat.messages": "📝 Messages",
    "logcat.voice": "🔊 Voice",
    "logcat.channels": "📁 Channels",
    "logcat.roles": "🎭 Roles",
    "logcat.server": "🛠️ Server",
    "logcat.actions": "✨ Actions",
    "logcat.modlogs": "🛡️ Mod Logs",

    "logev.members.join": "Entrata membro",
    "logev.members.leave": "Uscita membro",
    "logev.members.bot": "Bot aggiunto / rimosso",
    "logev.members.nickname": "Cambio nickname",
    "logev.members.avatar": "Avatar server cambiato",
    "logev.members.role_given": "Ruolo assegnato",
    "logev.members.role_taken": "Ruolo rimosso",
    "logev.messages.delete": "Messaggio cancellato",
    "logev.messages.bulk_delete": "Cancellazione multipla",
    "logev.messages.edit": "Messaggio modificato",
    "logev.messages.attachment": "Allegato cancellato (file/gif/audio)",
    "logev.messages.thread": "Thread creato / eliminato",
    "logev.messages.pin": "Messaggio fissato / rimosso",
    "logev.messages.reaction": "Reazione aggiunta / rimossa",
    "logev.voice.join_leave": "Entrata / Uscita / Spostamento",
    "logev.voice.mute_deaf": "Muta / Sordina",
    "logev.voice.stream_video": "Stream / Video",
    "logev.channels.create": "Canale creato",
    "logev.channels.delete": "Canale eliminato",
    "logev.channels.update": "Canale modificato",
    "logev.channels.permissions": "Permessi canale modificati",
    "logev.channels.webhook": "Webhook creato / eliminato / modificato",
    "logev.roles.create": "Ruolo creato",
    "logev.roles.delete": "Ruolo eliminato",
    "logev.roles.update": "Ruolo modificato",
    "logev.server.update": "Modifiche al server",
    "logev.server.boost": "Boost aggiunto / rimosso",
    "logev.actions.invite_create": "Invito creato",
    "logev.actions.invite_delete": "Invito eliminato",
    "logev.actions.emoji": "Emoji creata / eliminata / modificata",
    "logev.actions.event": "Evento creato / modificato / eliminato",
    "logev.modlogs.ban": "Ban / Unban",
    "logev.modlogs.kick": "Kick",
    "logev.modlogs.timeout": "Timeout / Untimeout",
    "logev.modlogs.lock": "Lock / Unlock canale",

    # ── ETICHETTE: antispam ─────────────────────────────────────────────────
    "spam.spam": "Spam",
    "spam.selfbot": "Spam con selfbot",
    "spam.mentions": "Spam di menzioni",
    "spam.links": "Spam di link",
    "spam.external": "Spam di comandi esterni",
    "spam.duplicates": "Spam di duplicati",
    "spam.important": "Spam importante",

    "sanction.none": "Nessuna (solo cancella)",
    "sanction.warn": "Warn",
    "sanction.timeout": "Timeout",
    "sanction.kick": "Kick",
    "sanction.softban": "Soft Ban",
    "sanction.ban": "Ban",

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

    # ── FUN (ship / matrimonio) ─────────────────────────────────────────────
    "fun.disabled": "🚫 Questa funzione non è disponibile al momento su questo server.",
    "fun.only_target": "❌ Solo la persona richiesta può accettare.",
    "fun.self_marry": "💍 Non puoi sposare te stesso! L'autostima è importante, "
                      "ma serve qualcun altro 😅",
    "fun.married": "💍 {a} e {b} si sono sposati per **24 ore**! 🎉💕",
    "fun.timeout": "⏳ {user} non ha accettato in tempo.",
    "fun.proposal": "{partner}, **{proposer}** vuole sposarti! 💍\n",
    "fun.single": "💔 {user} al momento è single.",
    "fun.marriage_title": "💍 Matrimonio",
    "fun.marriage_couple": "Coppia",
    "fun.marriage_expires": "Scade",
    # frasi di /ship, una per riga — {a} e {b} sono i due utenti
    "fun.ship_t0": "Ahia, le stelle dicono di scappare 🏃💨 {a} e {b} proprio no.\n"
                   "Mi dispiace {a}, ma {b} non fa per te 💀\n"
                   "Zero scintille tra {a} e {b}... meglio restare amici 🙈\n"
                   "Diciamo che {a} e {b} hanno gusti molto diversi 😬",
    "fun.ship_t1": "C'è speranza per {a} e {b}, continuate a provarci 💪\n"
                   "Qualcosina tra {a} e {b} c'è, ma serve lavorarci 🤏\n"
                   "Con un piccolo miracolo, {a} potrebbe conquistare {b} ✨\n"
                   "Non malissimo {a}... dai una chance a {b} 🤔",
    "fun.ship_t2": "A metà strada: {a} e {b}, chi lo sa come va a finire 💗\n"
                   "Qualche scintilla tra {a} e {b} si vede eccome 👀\n"
                   "Occhio, tra {a} e {b} potrebbe nascere qualcosa 🙂\n"
                   "Né caldo né freddo, ma {a} e {b} hanno del potenziale 🔥",
    "fun.ship_t3": "L'amore è nell'aria per {a} e {b} 🌸\n"
                   "Bella intesa! {a} e {b} ci siamo quasi 💕\n"
                   "Diciamocelo, {a} e {b} sono carini insieme 🥰\n"
                   "Occhi a cuore: {a} e {b} fanno una bella coppia 💘",
    "fun.ship_t4": "Ma come fate a non esservi ancora sposati, {a} e {b}? 💍\n"
                   "Sembrano fatti l'uno per l'altro: {a} e {b} 💞\n"
                   "Anime gemelle, {a} e {b} 🫶\n"
                   "Una coppia da favola: {a} e {b} 🏰",
    "fun.ship_t5": "Matrimonio in vista per {a} e {b}! 💍🔥\n"
                   "L'universo ha unito {a} e {b}, è destino ❤️🌌\n"
                   "Amore eterno scritto nelle stelle per {a} e {b} ⭐\n"
                   "Inseparabili per sempre: {a} e {b} ♾️",

    # ── LOG ─────────────────────────────────────────────────────────────────
    "logs.timeout_expired": "*Scaduto automaticamente*",

    # ── MINIGIOCHI ──────────────────────────────────────────────────────────
    "mg.disabled": "🚫 I minigiochi non sono disponibili al momento su questo server.",
    "mg.coin_heads": "Testa 🪙",
    "mg.coin_tails": "Croce ❌",
    "mg.coin_usage": "❌ Scegli **testa** o **croce**. Esempio: `+moneta testa`",
    "mg.coin_win": "🎉 Hai indovinato!",
    "mg.coin_lose": "😅 Hai sbagliato!",
    "mg.coin_result": "Hai scelto **{choice}**\nLa moneta è uscita: **{result}**\n{outcome}",
    "mg.8ball_usage": "❌ Scrivi una domanda. Esempio: `+8ball mi sposerò?`",
    "mg.8ball_title": "🎱 Palla Magica",
    "mg.8ball_question": "❓ Domanda",
    "mg.8ball_answer": "💬 Risposta",
    "mg.8ball_answers": "Sì, assolutamente! ✅\nNo, decisamente no. ❌\nForse... 🤔\n"
                        "Le stelle dicono sì. ⭐\nNon ci contare. 🚫\nTutto indica di sì. 👍\n"
                        "Le prospettive non sono buone. 😬\nChiedilo di nuovo più tardi. 🔄\n"
                        "È certo! 💯\nI segni puntano al no. 👎",
    "mg.rps_usage": "❌ Scegli **sasso**, **carta** o **forbice**. Esempio: `+rps sasso`",
    "mg.rps_rock": "Sasso",
    "mg.rps_paper": "Carta",
    "mg.rps_scissors": "Forbice",
    "mg.rps_title": "Carta, Forbice, Sasso",
    "mg.rps_you": "Tu",
    "mg.rps_bot": "Bot",
    "mg.rps_result": "Risultato",
    "mg.rps_draw": "Pareggio! 🤝",
    "mg.rps_win": "Hai vinto! 🎉",
    "mg.rps_lose": "Hai perso! 😅",
    "mg.guess_running": "⚠️ C'è già una partita in corso in questo canale! Usa `+tentativo <numero>`.",
    "mg.guess_started": "🎮 Ho pensato un numero tra **1 e 100**! Usa `+tentativo <numero>` per indovinare.",
    "mg.guess_need_number": "❌ Scrivi un numero. Esempio: `+tentativo 50`",
    "mg.guess_no_game": "❌ Nessuna partita in corso. Usa `+indovina` per iniziarne una.",
    "mg.guess_won_one": "🎉 **{user}** ha indovinato! Era **{number}** in {tries} tentativo!",
    "mg.guess_won_many": "🎉 **{user}** ha indovinato! Era **{number}** in {tries} tentativi!",
    "mg.guess_low": "📈 **{number}** è troppo basso! (Tentativo {tries})",
    "mg.guess_high": "📉 **{number}** è troppo alto! (Tentativo {tries})",

    # ── LIVELLI ─────────────────────────────────────────────────────────────
    "lvl.disabled": "❌ Il sistema livelli è disattivato.",
    "lvl.no_xp": "Nessuno ha ancora XP. 🤷",
    "lvl.leaderboard_title": "🏆 {guild} — Classifica",
    "lvl.xp_given": "✅ {verb} **{amount}** XP a {user}.",
    "lvl.xp_given_role": "✅ {verb} **{amount}** XP a **{count}** membri con {role}.",
    "lvl.xp_set": "✅ {user} ora ha **{xp}** XP (livello {level}).",
    "lvl.xp_reset": "✅ XP di {user} azzerati.",
    "lvl.xp_now": "Ora: **{xp}** XP (livello {level}).",
    "lvl.verb_given": "Dati",
    "lvl.verb_taken": "Tolti",

    # ── BENVENUTI / BOOST ───────────────────────────────────────────────────
    "greet.not_configured": "❌ Il messaggio **{type}** non è configurato. Usa `/set {type}`.",
    "greet.embed_gone": "❌ L'embed `{name}` non esiste più. Riconfigura con `/set {type}`.",
    "greet.send_error": "❌ Errore durante l'invio: {error}",
    "greet.sent": "✅ Messaggio inviato in {channel}.",
    "greet.embed_missing": "❌ L'embed `{name}` non esiste. Crealo con `/embed create`.",
    "greet.extra_message": "\nMessaggio: {msg}",
    "greet.welcome_set": "✅ Benvenuto impostato in {channel} con l'embed `{name}`.{extra}",
    "greet.boost_set": "✅ Messaggio di boost impostato in {channel} con l'embed `{name}`.{extra}",

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
