# db_customer.py
import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime

DB_PATH = Path(__file__).parent / 'customer_registry.sqlite3'

def ensure_schema() -> None:
    """テーブルがなければ作成"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS customer_registry (
                store_name TEXT PRIMARY KEY,
                first_seen_ym TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()

def get_first_seen(store_name: str) -> Optional[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute('SELECT first_seen_ym FROM customer_registry WHERE store_name = ?', (store_name,))
        row = cur.fetchone()
        return row[0] if row else None

def upsert_first_seen(store_name: str, ym: str) -> None:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute('SELECT first_seen_ym FROM customer_registry WHERE store_name = ?', (store_name,))
        row = cur.fetchone()
        if row is None:
            # 新規登録
            conn.execute('''
                INSERT INTO customer_registry (store_name, first_seen_ym, created_at)
                VALUES (?, ?, ?)
            ''', (store_name, ym, now))
        else:
            current_ym = row[0]
            # より古い年月なら更新
            if current_ym is None or ym < current_ym:
                conn.execute('''
                    UPDATE customer_registry SET first_seen_ym = ?, created_at = ? WHERE store_name = ?
                ''', (ym, now, store_name))
        conn.commit()
