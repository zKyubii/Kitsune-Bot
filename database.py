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
