import sqlite3
import os
from datetime import datetime, timezone
from backend.config import DATABASE_PATH, DATABASE_URL, CHAT_HISTORY_DEFAULT_LIMIT

# --- Database Engine Abstraction ---

_use_postgres = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


def _pg_connect():
    """Connect to PostgreSQL using DATABASE_URL."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _pg_dict_cursor(conn):
    import psycopg2.extras
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def get_connection():
    if _use_postgres:
        return _pg_connect()
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _execute(conn, sql, params=()):
    """Execute SQL with the right placeholder style."""
    if _use_postgres:
        # Convert ? placeholders to %s for PostgreSQL
        sql = sql.replace("?", "%s")
    cursor = conn.cursor() if not _use_postgres else _pg_dict_cursor(conn)
    cursor.execute(sql, params)
    return cursor


def _fetchall(conn, sql, params=()):
    if _use_postgres:
        sql = sql.replace("?", "%s")
        cur = _pg_dict_cursor(conn)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def init_db():
    conn = get_connection()
    if _use_postgres:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                avg_price REAL NOT NULL,
                added_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                notes TEXT DEFAULT '',
                added_at TEXT NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_ticker ON portfolio(ticker);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker);")
        conn.commit()
        cur.close()
    else:
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

            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                notes TEXT DEFAULT '',
                added_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chat_session
                ON chat_history(session_id);

            CREATE INDEX IF NOT EXISTS idx_portfolio_ticker
                ON portfolio(ticker);

            CREATE INDEX IF NOT EXISTS idx_watchlist_ticker
                ON watchlist(ticker);
        """)
        conn.commit()
    conn.close()


# --- Portfolio CRUD ---

def add_position(ticker: str, shares: float, avg_price: float) -> dict:
    conn = get_connection()
    cur = _execute(
        conn,
        "INSERT INTO portfolio (ticker, shares, avg_price, added_at) VALUES (?, ?, ?, ?)",
        (ticker.upper(), shares, avg_price, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return {"id": row_id, "ticker": ticker.upper(), "shares": shares, "avg_price": avg_price}


def get_portfolio() -> list[dict]:
    conn = get_connection()
    rows = _fetchall(conn, "SELECT * FROM portfolio ORDER BY added_at DESC")
    conn.close()
    return rows


def delete_position(position_id: int) -> bool:
    conn = get_connection()
    cur = _execute(conn, "DELETE FROM portfolio WHERE id = ?", (position_id,))
    conn.commit()
    deleted = cur.rowcount > 0
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
    sql = f"UPDATE portfolio SET {', '.join(updates)} WHERE id = ?"
    cur = _execute(conn, sql, params)
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


# --- Watchlist CRUD ---

def add_watchlist_item(ticker: str, notes: str = "") -> dict:
    conn = get_connection()
    try:
        cur = _execute(
            conn,
            "INSERT INTO watchlist (ticker, notes, added_at) VALUES (?, ?, ?)",
            (ticker.upper(), notes, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
        return {"id": row_id, "ticker": ticker.upper(), "notes": notes}
    except Exception:
        conn.rollback()
        raise ValueError(f"{ticker.upper()} is already in the watchlist")
    finally:
        conn.close()


def get_watchlist() -> list[dict]:
    conn = get_connection()
    rows = _fetchall(conn, "SELECT * FROM watchlist ORDER BY added_at DESC")
    conn.close()
    return rows


def remove_watchlist_item(ticker: str) -> bool:
    conn = get_connection()
    cur = _execute(conn, "DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# --- Chat History ---

def save_message(session_id: str, role: str, content: str):
    conn = get_connection()
    _execute(
        conn,
        "INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_chat_history(session_id: str, limit: int = None) -> list[dict]:
    if limit is None:
        limit = CHAT_HISTORY_DEFAULT_LIMIT
    conn = get_connection()
    rows = _fetchall(
        conn,
        "SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    )
    conn.close()
    return list(reversed(rows))
