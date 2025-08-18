# import_customer_registry.py
# CSV→SQLiteインポート
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / 'customer_registry.sqlite3'
CSV_PATH = Path(__file__).parent / 'customer_registry.csv'

def import_registry():
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM customer_registry')
        for _, row in df.iterrows():
            conn.execute('''
                INSERT INTO customer_registry (store_name, first_seen_ym, created_at)
                VALUES (?, ?, ?)
            ''', (row['store_name'], row['first_seen_ym'], row['created_at']))
        conn.commit()
    print(f'インポート完了: {DB_PATH}')

if __name__ == '__main__':
    import_registry()
