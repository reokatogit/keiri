# export_mapping_store.py
# SQLite→CSVエクスポート
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / 'mapping_store.sqlite3'
CSV_PATH = Path(__file__).parent / 'mapping_store.csv'

def export_mapping():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query('SELECT * FROM mapping_store', conn)
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    print(f'エクスポート完了: {CSV_PATH}')

if __name__ == '__main__':
    export_mapping()
