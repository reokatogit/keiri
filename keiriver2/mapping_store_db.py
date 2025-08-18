# mapping_store_db.py
# SQLite3によるmapping_store管理
import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime

DB_PATH = Path(__file__).parent / 'mapping_store.sqlite3'

def ensure_schema() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS mapping_store (
                cleaned TEXT PRIMARY KEY,
                normalized TEXT,
                field_name TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()

def load_mapping_store() -> dict[str, str]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute('SELECT cleaned, normalized FROM mapping_store')
        return {row[0]: row[1] for row in cur.fetchall()}

def append_mapping(cleaned: str, normalized: str, field_name: str) -> None:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO mapping_store (cleaned, normalized, field_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cleaned) DO UPDATE SET
                normalized=excluded.normalized,
                field_name=excluded.field_name,
                created_at=excluded.created_at
        ''', (cleaned, normalized, field_name, now))
        conn.commit()
