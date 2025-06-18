import os
import shutil
import pandas as pd
import time
import threading
from keiri_project.config import TEMP_ROOT, OUTPUT_ROOT, COLUMN_MAP
from keiri_project.normalizer import normalize_name, normalize_store_name
from keiri_project.rules import (
    parse_date, normalize_receiver,
    classify_entry, normalize_identifier,
    log_uncertain_case
)
from keiri_project.logger import finalize_unmatched
from keiri_project.merge_summarize import merge_and_aggregate  # 🔄 統合処理を呼び出し
from keiri_project.parser import parse_filename
from keiri_project.transformer import transform_file  # 仮想の処理関数

LAST_PROCESSED_FILE = os.path.join(OUTPUT_ROOT, "_last_updated.txt")


def process_group(dept: str, yyyymm: str):
    temp_dir = os.path.join(TEMP_ROOT, dept, yyyymm)
    if not os.path.isdir(temp_dir):
        return
    output_dir = os.path.join(OUTPUT_ROOT, dept, yyyymm)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    frames = []
    for fname in sorted(os.listdir(temp_dir)):
        path = os.path.join(temp_dir, fname)
        if fname.lower().endswith(('.xlsx', '.xls')):
            sheets = pd.read_excel(path, sheet_name=None)
            for sheet_name, df in sheets.items():
                df['__source_file'] = fname
                df['__sheet'] = sheet_name
                frames.append(df)
        elif fname.lower().endswith('.csv'):
            df = pd.read_csv(path, encoding='utf-8')
            df['__source_file'] = fname
            df['__sheet'] = ''
            frames.append(df)
    if not frames:
        return

    df_all = pd.concat(frames, ignore_index=True)
    df_all.columns = df_all.columns.str.strip().str.replace(r"[\n\r\t\u3000]", "", regex=True)

    df_all['部署名'] = dept

    date_col = next((c for c in df_all.columns if '日' in c and c != '部署名'), None)
    df_all['日付'] = df_all[date_col].astype(str).apply(lambda x: parse_date(x, fallback_year=int(yyyymm[:4])))

    name_keys = COLUMN_MAP['企業名']
    name_col = next((c for c in df_all.columns if any(k in c for k in name_keys)), None)
    df_all['企業名'] = df_all[name_col].astype(str).apply(
        lambda x: normalize_name(x, df_all['__source_file'].iloc[0], name_col, output_dir)
    ) if name_col else ''

    store_keys = COLUMN_MAP['店舗名']
    store_col = next((c for c in df_all.columns if any(k in c for k in store_keys)), None)
    df_all['店舗名'] = df_all[store_col].astype(str).apply(
        lambda x: normalize_store_name(x, df_all['__source_file'].iloc[0], store_col, output_dir)
    ) if store_col else ''

    df_all['送り先'] = df_all['店舗名'].apply(normalize_receiver)

    amt_keys = COLUMN_MAP['金額']
    amt_col = next((c for c in df_all.columns if any(k in c for k in amt_keys)), None)
    df_all['売上高'] = pd.to_numeric(df_all[amt_col], errors='coerce').fillna(0).astype(int) if amt_col else 0

    prod_keys = COLUMN_MAP['商品名']
    prod_col = next((c for c in df_all.columns if any(k in c for k in prod_keys)), None)
    if prod_col:
        raw_names = df_all[prod_col].astype(str)
        classified = raw_names.apply(classify_entry)
        df_all[['商品名', '作業項目']] = pd.DataFrame(list(classified), index=df_all.index)
    else:
        df_all['商品名'] = ''
        df_all['作業項目'] = ''

    num_keys = COLUMN_MAP['数量']
    num_col = next((c for c in df_all.columns if any(k in c for k in num_keys)), None)
    df_all['数量'] = pd.to_numeric(df_all[num_col], errors='coerce').fillna(0).astype(int) if num_col else 0

    price_keys = COLUMN_MAP['単価']
    price_col = next((c for c in df_all.columns if any(k in c for k in price_keys)), None)
    df_all['単価'] = pd.to_numeric(df_all[price_col], errors='coerce').fillna(0).astype(int) if price_col else 0

    df_all.loc[(df_all['作業項目'] != '') & (df_all['数量'] == 0), '数量'] = 1

    def set_classification(row):
        if row['商品名']:
            return '商品'
        if row['作業項目']:
            return '作業'
        return ''
    df_all['分類'] = df_all.apply(set_classification, axis=1)

    for id_col in ['伝票番号', '注文番号']:
        if id_col in df_all.columns:
            df_all[id_col] = df_all[id_col].apply(normalize_identifier)

    df_all.apply(lambda row: log_uncertain_case(row, '要GPT分類') if row['作業項目'] == '要GPT分類' else None, axis=1)

    fields = [
        '部署名', '日付', '企業名', '送り先',
        '商品名', '作業項目', '分類', '数量', '単価', '売上高', '注文番号', '伝票番号'
    ]
    rec = df_all[fields]
    rec.to_csv(os.path.join(output_dir, 'records.csv'), index=False)
    rec.to_excel(os.path.join(output_dir, 'records.xlsx'), index=False)
    rec.to_csv(os.path.join(output_dir, 'summary.csv'), index=False)
    rec.to_excel(os.path.join(output_dir, 'summary.xlsx'), index=False)

    finalize_unmatched(output_dir)

    # ✅ 統合用の「処理時間ファイル」を更新
    with open(LAST_PROCESSED_FILE, 'w') as f:
        f.write(str(time.time()))


def start_merge_summary_watcher(interval_sec=5, cooldown_sec=15):
    """
    OUTPUT_ROOT/_last_updated.txt の更新を監視し、
    最後の処理から cooldown_sec 秒経過したら summary を自動統合。
    """
    def watcher():
        last_merged = 0
        ts_path = LAST_PROCESSED_FILE
        while True:
            try:
                if os.path.exists(ts_path):
                    with open(ts_path, 'r') as f:
                        ts = float(f.read().strip())
                    now = time.time()
                    if ts > last_merged and (now - ts >= cooldown_sec):
                        print("🌀 統合summaryを自動再生成します...")
                        merge_and_aggregate()
                        last_merged = now
            except Exception as e:
                print(f"⚠️ 自動統合中にエラー: {e}")
            time.sleep(interval_sec)

    threading.Thread(target=watcher, daemon=True).start()


def handle_new_file(file_path):
    # ファイルパスから部署名・年月・企業名などを抽出して処理開始
    print(f"🛠 処理開始: {file_path}")
    file_info = parse_filename(file_path)
    if file_info is None:
        print("⚠️ ファイル名が不正のためスキップ")
        return
    transform_file(file_path, file_info)
