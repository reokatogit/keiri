# import_mapping_store.py
# CSV→SQLiteインポート
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / 'mapping_store.sqlite3'
CSV_PATH = Path(__file__).parent / 'mapping_store.csv'

def import_mapping():
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM mapping_store')
        for _, row in df.iterrows():
            conn.execute('''
                INSERT INTO mapping_store (cleaned, normalized, field_name, created_at)
                VALUES (?, ?, ?, ?)
            ''', (row['cleaned'], row['normalized'], row['field_name'], row['created_at']))
        conn.commit()
    print(f'インポート完了: {DB_PATH}')

if __name__ == '__main__':
    import_mapping()
