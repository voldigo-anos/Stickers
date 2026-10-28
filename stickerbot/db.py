import os
import sqlite3
import threading
import time

from config import DB_PATH

_lock = threading.Lock()
_conn = None


def init():
    global _conn
    directory = os.path.dirname(os.path.abspath(DB_PATH))
    if directory:
        os.makedirs(directory, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    _conn.row_factory = sqlite3.Row
    with _lock:
        # WAL rend les écritures plus sûres et évite qu'une lecture bloque le bot.
        _conn.execute('PRAGMA journal_mode=WAL')
        _conn.execute('PRAGMA synchronous=FULL')
        _conn.execute('PRAGMA busy_timeout=30000')
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                banned      INTEGER NOT NULL DEFAULT 0,
                joined_at   INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS packs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                name        TEXT NOT NULL UNIQUE,
                title       TEXT NOT NULL,
                created_at  INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pack_stickers (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                pack_id          INTEGER NOT NULL,
                file_unique_id   TEXT NOT NULL,
                added_at         INTEGER NOT NULL,
                UNIQUE (pack_id, file_unique_id)
            );
            CREATE INDEX IF NOT EXISTS idx_packs_user ON packs (user_id);
            """
        )
        # migrations : forme du sticker + ecriture (watermark) par pack
        for column, ddl in (
            ('watermark_color', "ALTER TABLE packs ADD COLUMN watermark_color TEXT NOT NULL DEFAULT '#FFFFFF'"),
            ('shape', "ALTER TABLE packs ADD COLUMN shape TEXT NOT NULL DEFAULT 'original'"),
            ('watermark', "ALTER TABLE packs ADD COLUMN watermark TEXT NOT NULL DEFAULT ''"),
        ):
            try:
                _conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # colonne deja presente
        _conn.commit()


def _exec(query, params=(), fetch=None):
    with _lock:
        cur = _conn.execute(query, params)
        if fetch == 'one':
            row = cur.fetchone()
        elif fetch == 'all':
            row = cur.fetchall()
        else:
            row = cur.lastrowid
        _conn.commit()
        return row


# ---------- users ----------

def save_user(user):
    _exec(
        'INSERT INTO users (user_id, username, first_name, joined_at) VALUES (?, ?, ?, ?) '
        'ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name',
        (user.id, user.username, user.first_name, int(time.time())),
    )


def is_banned(user_id: int) -> bool:
    row = _exec('SELECT banned FROM users WHERE user_id = ?', (user_id,), 'one')
    return bool(row and row['banned'])


def set_banned(user_id: int, banned: bool):
    _exec('INSERT OR IGNORE INTO users (user_id, joined_at) VALUES (?, ?)', (user_id, int(time.time())))
    _exec('UPDATE users SET banned = ? WHERE user_id = ?', (1 if banned else 0, user_id))


def all_user_ids():
    return [r['user_id'] for r in _exec('SELECT user_id FROM users WHERE banned = 0', (), 'all')]


# ---------- packs ----------

def add_pack(user_id: int, name: str, title: str, shape: str = 'original', watermark: str = '', watermark_color: str = '#FFFFFF') -> int:
    return _exec(
        'INSERT INTO packs (user_id, name, title, shape, watermark, watermark_color, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (user_id, name, title, shape, watermark or '', watermark_color, int(time.time())),
    )


def set_pack_style(pack_id: int, shape: str, watermark: str, watermark_color: str = '#FFFFFF'):
    _exec('UPDATE packs SET shape = ?, watermark = ?, watermark_color = ? WHERE id = ?', (shape, watermark or '', watermark_color, pack_id))


def get_pack(user_id: int, name: str):
    return _exec('SELECT * FROM packs WHERE user_id = ? AND name = ?', (user_id, name), 'one')


def get_pack_by_name(name: str):
    return _exec('SELECT * FROM packs WHERE name = ?', (name,), 'one')


def user_packs(user_id: int):
    return _exec(
        'SELECT p.*, (SELECT COUNT(*) FROM pack_stickers s WHERE s.pack_id = p.id) AS count '
        'FROM packs p WHERE p.user_id = ? ORDER BY p.created_at DESC',
        (user_id,),
        'all',
    )


def delete_pack(pack_id: int):
    _exec('DELETE FROM pack_stickers WHERE pack_id = ?', (pack_id,))
    _exec('DELETE FROM packs WHERE id = ?', (pack_id,))


# ---------- stickers ----------

def has_sticker(pack_id: int, file_unique_id: str) -> bool:
    row = _exec(
        'SELECT 1 FROM pack_stickers WHERE pack_id = ? AND file_unique_id = ?',
        (pack_id, file_unique_id),
        'one',
    )
    return row is not None


def add_sticker(pack_id: int, file_unique_id: str):
    _exec(
        'INSERT OR IGNORE INTO pack_stickers (pack_id, file_unique_id, added_at) VALUES (?, ?, ?)',
        (pack_id, file_unique_id, int(time.time())),
    )


def remove_sticker(pack_id: int, file_unique_id: str):
    _exec('DELETE FROM pack_stickers WHERE pack_id = ? AND file_unique_id = ?', (pack_id, file_unique_id))


def pack_count(pack_id: int) -> int:
    row = _exec('SELECT COUNT(*) AS c FROM pack_stickers WHERE pack_id = ?', (pack_id,), 'one')
    return row['c'] if row else 0


# ---------- stats / classement ----------

def leaderboard(limit: int = 10):
    return _exec(
        """
        SELECT u.user_id,
               COALESCE(u.username, '')   AS username,
               COALESCE(u.first_name, '') AS first_name,
               COUNT(DISTINCT p.id)       AS packs,
               COUNT(s.id)                AS stickers
        FROM packs p
        JOIN users u ON u.user_id = p.user_id
        LEFT JOIN pack_stickers s ON s.pack_id = p.id
        GROUP BY u.user_id
        ORDER BY stickers DESC, packs DESC
        LIMIT ?
        """,
        (limit,),
        'all',
    )


def user_rank(user_id: int):
    rows = leaderboard(1000)
    for i, row in enumerate(rows, start=1):
        if row['user_id'] == user_id:
            return i, row
    return None, None


def global_stats():
    users = _exec('SELECT COUNT(*) AS c FROM users', (), 'one')['c']
    banned = _exec('SELECT COUNT(*) AS c FROM users WHERE banned = 1', (), 'one')['c']
    packs = _exec('SELECT COUNT(*) AS c FROM packs', (), 'one')['c']
    stickers = _exec('SELECT COUNT(*) AS c FROM pack_stickers', (), 'one')['c']
    return {'users': users, 'banned': banned, 'packs': packs, 'stickers': stickers}
