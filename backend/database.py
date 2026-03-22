import sqlite3
import os
from datetime import datetime
from backend.config import DATABASE_PATH


def get_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            shares REAL NOT NULL,
            avg_price REAL NOT NULL,
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chat_session
            ON chat_history(session_id);

        CREATE INDEX IF NOT EXISTS idx_portfolio_ticker
            ON portfolio(ticker);
    """)
    conn.commit()
    conn.close()


# --- Portfolio CRUD ---

def add_position(ticker: str, shares: float, avg_price: float) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO portfolio (ticker, shares, avg_price, added_at) VALUES (?, ?, ?, ?)",
        (ticker.upper(), shares, avg_price, datetime.utcnow().isoformat()),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return {"id": row_id, "ticker": ticker.upper(), "shares": shares, "avg_price": avg_price}


def get_portfolio() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM portfolio ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_position(position_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio WHERE id = ?", (position_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def update_position(position_id: int, shares: float = None, avg_price: float = None) -> bool:
    conn = get_connection()
    updates = []
    params = []
    if shares is not None:
        updates.append("shares = ?")
        params.append(shares)
    if avg_price is not None:
        updates.append("avg_price = ?")
        params.append(avg_price)
    if not updates:
        conn.close()
        return False
    params.append(position_id)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE portfolio SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# --- Chat History ---

def save_message(session_id: str, role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_chat_history(session_id: str, limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
