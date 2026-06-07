# 🤖 Discord Bot

## Struttura
```
discord-bot/
├── main.py              # Avvio del bot
├── requirements.txt     # Dipendenze
├── .env                 # Token (non condividere mai!)
└── cogs/
    ├── moderation.py    # Comandi di moderazione
    └── minigames.py     # Minigiochi
```

## Setup

1. Installa le dipendenze:
   ```
   pip install -r requirements.txt
   ```

2. Metti il tuo token nel file `.env`:
   ```
   DISCORD_TOKEN=il_tuo_token_qui
   ```

3. Avvia il bot:
   ```
   python main.py
   ```

## Comandi Moderazione
| Comando | Descrizione |
|---------|-------------|
| `/ban` | Banna un utente |
| `/unban` | Sbanna un utente tramite ID |
| `/kick` | Kicka un utente |
| `/timeout` | Mette in timeout un utente |
| `/untimeout` | Rimuove il timeout |
| `/clear` | Elimina messaggi (max 100) |
| `/slowmode` | Imposta slowmode nel canale |

## Comandi Minigiochi
| Comando | Descrizione |
|---------|-------------|
| `/dado` | Lancia un dado (personalizza le facce) |
| `/moneta` | Testa o croce |
| `/8ball` | Palla magica |
| `/rps` | Carta, forbice, sasso |
| `/indovina` | Indovina il numero (1-100) |
| `/tentativo` | Fai un tentativo nel gioco indovina |

## Come aggiungere funzioni con Claude Code
Apri la cartella del progetto nel terminale e di' a Claude Code cosa vuoi:
- *"Aggiungi un sistema di warn con contatore"*
- *"Crea un gioco trivia con domande casuali"*
- *"Aggiungi un log channel per le azioni di moderazione"*
