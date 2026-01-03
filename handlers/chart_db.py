import sqlite3
from typing import Optional, Any
from handlers.chart_normalizer import normalize_fa

DB_PATH = "charts.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS charts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        major_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        file_id TEXT NOT NULL,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL
    );
    """)
    conn.commit()
    conn.close()


def add_chart(major_name: str, file_id: str, chat_id: int, message_id: int) -> int:
    n = normalize_fa(major_name)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO charts (major_name, normalized_name, file_id, chat_id, message_id)
        VALUES (?, ?, ?, ?, ?)
    """, (major_name, n, file_id, chat_id, message_id))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_all_for_search():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, major_name, normalized_name FROM charts")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chart_by_id(chart_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM charts WHERE id = ?", (chart_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_chart(chart_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted
