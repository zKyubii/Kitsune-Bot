import sqlite3
import os
import json
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "kitsune.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row


def init_db():
    """Crea le tabelle se non esistono. Chiamata all'avvio del bot."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id            INTEGER PRIMARY KEY,
            confession_channel  INTEGER,
            log_channel         INTEGER,
            confession_count    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS confessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER,
            number      INTEGER,
            user_id     INTEGER,
            message_id  INTEGER,
            content     TEXT,
            reply_to    INTEGER,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS marriages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER,
            user1       INTEGER,
            user2       INTEGER,
            created_at  TEXT,
            expires_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS log_config (
            guild_id    INTEGER PRIMARY KEY,
            config      TEXT
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id      INTEGER,
            user_id       INTEGER,
            moderator_id  INTEGER,
            reason        TEXT,
            proof         TEXT,
            created_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS jailed (
            guild_id  INTEGER,
            user_id   INTEGER,
            roles     TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS embeds (
            guild_id  INTEGER,
            name      TEXT,
            data      TEXT,
            PRIMARY KEY (guild_id, name)
        );

        CREATE TABLE IF NOT EXISTS partnerships (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     INTEGER,
            channel_id   INTEGER,
            message_ids  TEXT,
            author_id    INTEGER,
            manager_id   INTEGER,
            created_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS levels (
            guild_id  INTEGER,
            user_id   INTEGER,
            xp        INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            user_id  INTEGER PRIMARY KEY,
            data     TEXT
        );

        CREATE TABLE IF NOT EXISTS temp_bans (
            guild_id  INTEGER,
            user_id   INTEGER,
            unban_at  TEXT,
            reason    TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     INTEGER,
            channel_id   INTEGER,
            panel_key    TEXT,
            opener_id    INTEGER,
            claimer_id   INTEGER,
            number       INTEGER,
            created_at   TEXT,
            closed_at    TEXT,
            status       TEXT DEFAULT 'open'
        );
    """)
    conn.commit()


# ── CONFESSION ──────────────────────────────────────────────────────────────
def set_confession_channels(guild_id: int, channel_id: int, log_id: int | None):
    conn.execute(
        """
        INSERT INTO guild_config (guild_id, confession_channel, log_channel)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            confession_channel = excluded.confession_channel,
            log_channel        = excluded.log_channel
        """,
        (guild_id, channel_id, log_id),
    )
    conn.commit()


def get_config(guild_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
    ).fetchone()


def next_confession_number(guild_id: int) -> int:
    conn.execute(
        "UPDATE guild_config SET confession_count = confession_count + 1 WHERE guild_id = ?",
        (guild_id,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT confession_count FROM guild_config WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    return row["confession_count"]


def save_confession(guild_id: int, number: int, user_id: int, message_id: int,
                    content: str, reply_to: int | None):
    conn.execute(
        """
        INSERT INTO confessions (guild_id, number, user_id, message_id, content, reply_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (guild_id, number, user_id, message_id, content, reply_to,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()


# ── MARRIAGES ───────────────────────────────────────────────────────────────
def add_marriage(guild_id: int, user1: int, user2: int, hours: int = 24):
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(hours=hours)
    # Rimuove eventuali matrimoni precedenti dei due utenti in questo server
    conn.execute(
        "DELETE FROM marriages WHERE guild_id = ? AND (user1 IN (?, ?) OR user2 IN (?, ?))",
        (guild_id, user1, user2, user1, user2),
    )
    conn.execute(
        "INSERT INTO marriages (guild_id, user1, user2, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (guild_id, user1, user2, now.isoformat(), expires.isoformat()),
    )
    conn.commit()
    return expires


def get_marriage(guild_id: int, user_id: int) -> sqlite3.Row | None:
    """Restituisce il matrimonio attivo (non scaduto) dell'utente, se esiste."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return conn.execute(
        """
        SELECT * FROM marriages
        WHERE guild_id = ? AND (user1 = ? OR user2 = ?) AND expires_at > ?
        """,
        (guild_id, user_id, user_id, now),
    ).fetchone()


# ── LOG / DASHBOARD CONFIG ──────────────────────────────────────────────────
def get_log_config(guild_id: int) -> dict:
    row = conn.execute(
        "SELECT config FROM log_config WHERE guild_id = ?", (guild_id,)
    ).fetchone()
    if row and row["config"]:
        try:
            return json.loads(row["config"])
        except json.JSONDecodeError:
            return {}
    return {}


def save_log_config(guild_id: int, config: dict):
    conn.execute(
        """
        INSERT INTO log_config (guild_id, config) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET config = excluded.config
        """,
        (guild_id, json.dumps(config)),
    )
    conn.commit()


# ── WARNINGS ────────────────────────────────────────────────────────────────
def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str, proof: str | None) -> int:
    cur = conn.execute(
        """
        INSERT INTO warnings (guild_id, user_id, moderator_id, reason, proof, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (guild_id, user_id, moderator_id, reason, proof,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_warnings(guild_id: int, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id",
        (guild_id, user_id),
    ).fetchall()


def remove_warning(guild_id: int, warn_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM warnings WHERE guild_id = ? AND id = ?", (guild_id, warn_id)
    )
    conn.commit()
    return cur.rowcount > 0


def clear_warnings(guild_id: int, user_id: int) -> int:
    cur = conn.execute(
        "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
    )
    conn.commit()
    return cur.rowcount


# ── JAIL ────────────────────────────────────────────────────────────────────
def set_jailed(guild_id: int, user_id: int, role_ids: list):
    conn.execute(
        """
        INSERT INTO jailed (guild_id, user_id, roles) VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET roles = excluded.roles
        """,
        (guild_id, user_id, json.dumps(role_ids)),
    )
    conn.commit()


def get_jailed(guild_id: int, user_id: int):
    row = conn.execute(
        "SELECT roles FROM jailed WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
    ).fetchone()
    if row:
        return json.loads(row["roles"])
    return None


def remove_jailed(guild_id: int, user_id: int):
    conn.execute("DELETE FROM jailed WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    conn.commit()


# ── EMBED BUILDER ───────────────────────────────────────────────────────────
def save_embed(guild_id: int, name: str, data: dict):
    conn.execute(
        """
        INSERT INTO embeds (guild_id, name, data) VALUES (?, ?, ?)
        ON CONFLICT(guild_id, name) DO UPDATE SET data = excluded.data
        """,
        (guild_id, name, json.dumps(data)),
    )
    conn.commit()


def get_embed(guild_id: int, name: str):
    row = conn.execute(
        "SELECT data FROM embeds WHERE guild_id = ? AND name = ?", (guild_id, name)
    ).fetchone()
    if row:
        return json.loads(row["data"])
    return None


def list_embeds(guild_id: int) -> list:
    rows = conn.execute(
        "SELECT name FROM embeds WHERE guild_id = ? ORDER BY name", (guild_id,)
    ).fetchall()
    return [r["name"] for r in rows]


def delete_embed(guild_id: int, name: str) -> bool:
    cur = conn.execute("DELETE FROM embeds WHERE guild_id = ? AND name = ?", (guild_id, name))
    conn.commit()
    return cur.rowcount > 0


# ── PARTNERSHIP ─────────────────────────────────────────────────────────────
def add_partnership(guild_id: int, channel_id: int, message_ids: list,
                    author_id: int, manager_id: int | None):
    conn.execute(
        """
        INSERT INTO partnerships (guild_id, channel_id, message_ids, author_id, manager_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (guild_id, channel_id, json.dumps(message_ids), author_id, manager_id,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()


def get_partnerships_by_user(guild_id: int, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM partnerships WHERE guild_id = ? AND (author_id = ? OR manager_id = ?)",
        (guild_id, user_id, user_id),
    ).fetchall()


def delete_partnership(pid: int):
    conn.execute("DELETE FROM partnerships WHERE id = ?", (pid,))
    conn.commit()


# ── LIVELLI ─────────────────────────────────────────────────────────────────
def get_xp(guild_id: int, user_id: int) -> int:
    row = conn.execute(
        "SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
    ).fetchone()
    return row["xp"] if row else 0


def set_xp(guild_id: int, user_id: int, xp: int) -> int:
    xp = max(0, int(xp))
    conn.execute(
        """
        INSERT INTO levels (guild_id, user_id, xp) VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp
        """,
        (guild_id, user_id, xp),
    )
    conn.commit()
    return xp


def add_xp(guild_id: int, user_id: int, amount: int) -> int:
    return set_xp(guild_id, user_id, get_xp(guild_id, user_id) + int(amount))


def reset_level_user(guild_id: int, user_id: int):
    conn.execute("DELETE FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    conn.commit()


def level_top(guild_id: int, limit: int, offset: int = 0) -> list:
    return conn.execute(
        "SELECT user_id, xp FROM levels WHERE guild_id = ? AND xp > 0 "
        "ORDER BY xp DESC LIMIT ? OFFSET ?",
        (guild_id, limit, offset),
    ).fetchall()


def level_rank(guild_id: int, user_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) + 1 AS r FROM levels
        WHERE guild_id = ? AND xp > (SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?)
        """,
        (guild_id, guild_id, user_id),
    ).fetchone()
    return row["r"] if row else 1


# ── PROFILO UTENTE (globale, non legato al server) ──────────────────────────
def get_user_profile(user_id: int) -> dict:
    row = conn.execute(
        "SELECT data FROM user_profile WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row and row["data"]:
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return {}
    return {}


def save_user_profile(user_id: int, data: dict):
    conn.execute(
        """
        INSERT INTO user_profile (user_id, data) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET data = excluded.data
        """,
        (user_id, json.dumps(data)),
    )
    conn.commit()


# ── BAN TEMPORANEI ──────────────────────────────────────────────────────────
# La scadenza sta nel DB (non in un task in memoria) così i ban temporanei
# vengono sbloccati anche se il bot viene riavviato nel frattempo.
def add_temp_ban(guild_id: int, user_id: int, scadenza: datetime.datetime, durata: str = None):
    conn.execute(
        """
        INSERT INTO temp_bans (guild_id, user_id, unban_at, reason) VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            unban_at = excluded.unban_at,
            reason   = excluded.reason
        """,
        (guild_id, user_id, scadenza.isoformat(), durata),
    )
    conn.commit()


def remove_temp_ban(guild_id: int, user_id: int):
    conn.execute(
        "DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
    )
    conn.commit()


def get_expired_temp_bans() -> list:
    """Ban temporanei la cui scadenza è già passata."""
    adesso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return conn.execute(
        "SELECT * FROM temp_bans WHERE unban_at <= ?", (adesso,)
    ).fetchall()


# ── TICKETS ─────────────────────────────────────────────────────────────────
def create_ticket(guild_id: int, channel_id: int, panel_key: str,
                  opener_id: int, number: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO tickets (guild_id, channel_id, panel_key, opener_id, number, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (guild_id, channel_id, panel_key, opener_id, number,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_ticket_by_channel(channel_id: int):
    return conn.execute(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'", (channel_id,)
    ).fetchone()


def set_ticket_claimer(channel_id: int, claimer_id):
    conn.execute("UPDATE tickets SET claimer_id = ? WHERE channel_id = ?",
                 (claimer_id, channel_id))
    conn.commit()


def close_ticket(channel_id: int):
    conn.execute(
        "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(), channel_id),
    )
    conn.commit()


def count_open_tickets(guild_id: int, user_id: int = None) -> int:
    if user_id is None:
        row = conn.execute(
            "SELECT COUNT(*) c FROM tickets WHERE guild_id = ? AND status = 'open'",
            (guild_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) c FROM tickets WHERE guild_id = ? AND opener_id = ? AND status = 'open'",
            (guild_id, user_id)).fetchone()
    return row["c"] if row else 0


def open_ticket_channels(guild_id: int) -> list:
    """Id dei canali dei ticket aperti (per pulizia all'avvio)."""
    return [r["channel_id"] for r in conn.execute(
        "SELECT channel_id FROM tickets WHERE guild_id = ? AND status = 'open'", (guild_id,)
    ).fetchall()]
