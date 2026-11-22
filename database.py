"""楽曲・投稿履歴を管理する SQLite データベース操作。

選曲は「サイクル」単位で行う。
1サイクルの間は同じ曲を重複して投稿せず、全曲を投稿し終えたら次のサイクルへ進む。
"""

import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    song_id     TEXT PRIMARY KEY,           -- 「ソース名:ID」形式（例: youtube:xxxxxxxxxxx）
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    artist      TEXT,
    description TEXT,
    is_active   INTEGER DEFAULT 1,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS state (
    id    INTEGER PRIMARY KEY CHECK(id = 1),
    cycle INTEGER NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO state (id, cycle) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id   TEXT NOT NULL,
    cycle     INTEGER NOT NULL,
    posted_at TEXT NOT NULL,
    note_id   TEXT
);
"""

# v1（YouTube 専用の video_id 列）から v2（複数ソース対応）への移行
MIGRATE_V1_TO_V2 = """
BEGIN;
ALTER TABLE songs RENAME COLUMN video_id TO song_id;
ALTER TABLE songs ADD COLUMN source TEXT NOT NULL DEFAULT 'youtube';
ALTER TABLE songs ADD COLUMN url TEXT NOT NULL DEFAULT '';
UPDATE songs SET
    url = 'https://www.youtube.com/watch?v=' || song_id,
    song_id = 'youtube:' || song_id;
ALTER TABLE history RENAME COLUMN video_id TO song_id;
UPDATE history SET song_id = 'youtube:' || song_id;
PRAGMA user_version = 2;
COMMIT;
"""


@contextmanager
def connect():
    """接続を開き、正常終了ならコミット、例外ならロールバックして必ず閉じる。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def initialize():
    """テーブルを作成し、古い形式の DB なら新しい形式に移行する。"""
    with connect() as conn:
        if "video_id" in _columns(conn, "songs"):
            backup = DB_PATH.with_name(DB_PATH.name + ".v1.bak")
            shutil.copy2(DB_PATH, backup)
            logger.info("DB を新しい形式に移行します（バックアップ: %s）", backup)
            conn.executescript(MIGRATE_V1_TO_V2)

        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _current_cycle(conn):
    return conn.execute("SELECT cycle FROM state WHERE id = 1").fetchone()["cycle"]


def get_cycle():
    with connect() as conn:
        return _current_cycle(conn)


def get_random_song():
    """今のサイクルでまだ投稿していない曲をランダムに1曲返す。

    全曲投稿済みならサイクルを1つ進めてから選ぶ。
    有効な曲が1曲もなければ None を返す。
    """
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cycle = _current_cycle(conn)

        song = conn.execute(
            """
            SELECT * FROM songs
            WHERE is_active = 1
              AND song_id NOT IN (SELECT song_id FROM history WHERE cycle = ?)
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (cycle,),
        ).fetchone()

        if song is None:
            song = conn.execute(
                "SELECT * FROM songs WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1"
            ).fetchone()

            if song is None:
                return None

            conn.execute("UPDATE state SET cycle = cycle + 1 WHERE id = 1")

        return dict(song)


def record_success(song_id, note_id=None):
    """投稿に成功した曲を現在のサイクルの履歴に記録する。"""
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            "INSERT INTO history (song_id, cycle, posted_at, note_id) VALUES (?, ?, ?, ?)",
            (song_id, _current_cycle(conn), now, note_id),
        )


def get_history_count():
    """現在のサイクルで投稿済みの曲数を返す。"""
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM history WHERE cycle = ?",
            (_current_cycle(conn),),
        ).fetchone()[0]


def upsert_songs(songs):
    """楽曲リスト（sources.Song）を DB に反映する。

    songs に含まれない既存曲は is_active = 0（投稿対象外）になる。
    """
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute("UPDATE songs SET is_active = 0")
        conn.executemany(
            """
            INSERT INTO songs (song_id, source, title, url, artist, description, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(song_id) DO UPDATE SET
                source      = excluded.source,
                title       = excluded.title,
                url         = excluded.url,
                artist      = excluded.artist,
                description = excluded.description,
                is_active   = 1,
                updated_at  = excluded.updated_at
            """,
            [
                (s.id, s.source, s.title, s.url, s.artist, s.description, now)
                for s in songs
            ],
        )
