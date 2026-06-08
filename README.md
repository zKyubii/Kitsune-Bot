# 🦊 Kitsune Bot

Bot Discord multifunzione: moderazione avanzata, antispam, logging completo, sistema di log stile Quark, embed builder, benvenuti, confessioni anonime e minigiochi — tutto configurabile da una **dashboard interattiva**.

---

## ✨ Funzionalità principali

### 🛡️ Moderazione
- **Ban / Softban / Hackban** (con durata, motivo, prove, purge messaggi)
- **Kick · Timeout · Untimeout · Unban**
- **Warn** con motivo/prove + **regole automatiche** (a N warn → timeout/kick/ban)
- **Jail** — sistema di isolamento (ruolo + canale dedicato, auto-nascondi nuovi canali)
- **Lock / Unlock** canali · **Slowmode** · **Clear** con filtri (utente/link/immagini/bot)
- **Banlist · Serverinfo · Userinfo** (stile Wick)

### 🚨 Antispam & Sicurezza
- 7 categorie (spam, menzioni, link, duplicati, selfbot, comandi esterni, spam grave) con **sanzioni configurabili**
- **Anti-scam** sui link/truffe · **Whitelist** canali/ruoli/utenti
- **DM Lock** e **Join Lock** (Pausa DM / Pausa inviti nativi di Discord)

### 📋 Logging (stile Quark)
Categorie: **Members · Messages · Voice · Channels · Roles · Server · Actions · Mod Logs**
- Canale e singoli eventi attivabili per categoria
- Allegati (file/gif/audio), reazioni, pin, thread, webhook, eventi, permessi canale
- Voice diviso in 3 (join/leave · mute/deaf · stream) con **durata permanenza**
- Tracking inviti all'ingresso · pulsante **Copia ID** · **blacklist canali**

### 🎭 Ruoli
- `/role add · remove · all · humans · bots`
- **Autorole** all'ingresso (dalla dashboard)
- Permessi comandi moderazione configurabili per ruolo

### 📝 Embed Builder
- `/embed create · edit · list · delete · send` con **preview live** e modali
- Variabili dinamiche (`{user}`, `{user_avatar}`, `{server_membercount}`, ...)

### 👋 Benvenuti & Boost
- `/set greet · /set boost` + `/test greet · /test boost` (usano un embed salvato)

### 🤫 Confessioni anonime
- `/confession write` + pulsante "Invia una confessione!" · log staff anti-abuso

### 🎉 Fun & Minigiochi
- `/ship` (immagine generata + Pair/matrimonio 24h) · `/marriage`
- **Make it a Quote** (tasto destro o `?quote`)
- `/dado · /moneta · /8ball · /rps · /indovina`

### ⚙️ Dashboard
`/dashboard` — pannello interattivo per configurare **tutto** (Log, Funzioni, Moderazione).

---

## 📁 Struttura
```
Kitsune Bot/
├── main.py            # Avvio + sync comandi
├── database.py        # Database SQLite condiviso
├── logconfig.py       # Categorie log e helper
├── requirements.txt   # Dipendenze
├── .env               # Token (NON condividere mai!)
└── cogs/
    ├── moderation.py      ├── antispam.py
    ├── logs.py            ├── dashboard.py
    ├── roles.py           ├── embedbuilder.py
    ├── greetings.py       ├── confession.py
    ├── fun.py             ├── quote.py
    └── minigames.py
```

---

## 🚀 Setup

1. Installa le dipendenze:
   ```
   pip install -r requirements.txt
   ```
2. Inserisci il token nel file `.env`:
   ```
   DISCORD_TOKEN=il_tuo_token_qui
   GUILD_ID=id_server   # opzionale: sync istantanea (vuoto = globale)
   ```
3. Avvia:
   ```
   python main.py
   ```

> Richiede i **Privileged Intents** (Server Members + Message Content) attivi nel Developer Portal.
