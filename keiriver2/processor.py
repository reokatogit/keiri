import os
import pandas as pd
import unicodedata
import re
from collections import Counter
from rapidfuzz import process, fuzz
from plyer import notification
from config import (
    WATCH_DIR, OUTPUT_DIR, PROCESSED_DIR,
    COMPANY_DICT_PATH, STORE_DICT_PATH, STORE_MAPPING_PATH,
    CLIENT_DICT_PATH, CUSTOMER_DICT_PATH, SHIPTO_DICT_PATH,
    COLUMN_ALIASES, VALID_EXTENSIONS
)
from parser import parse_filename
from logger import log_unmatched

# ─── ユーティリティ群 ───

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ヘッダーの表記ゆれを標準列名に揃える"""
    rename_map = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = std
    return df.rename(columns=rename_map)

def load_mapping_dict(path: str) -> dict[str,str]:
    """辞書CSVを読み込み {表記:標準化} マップを返す"""
    if os.path.exists(path):
        d = pd.read_csv(path, dtype=str)
        return dict(zip(d['表記'], d['標準化']))
    return {}

def call_chatgpt(prompt: str, category: str) -> str | None:
    """ChatGPTに問い合わせて標準化or補完。失敗時はログのみ"""
    try:
        import openai
        if not getattr(openai, "api_key", None):
            return None
        resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role":"user","content":prompt}],
            max_tokens=20
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log_unmatched(f"{category}APIエラー", str(e))
        return None

def clean_string(s: str) -> str:
    """最小限の文字列正規化：NFKC＋空白＆記号揃え"""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("‐","-").replace("–","-").replace("—","-").replace("―","-")
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def normalize_field(orig: str, mapping: dict[str,str], dict_path: str, field_name: str) -> str:
    """辞書→ファジー→API→ログ の順で標準化し、辞書追記も行う"""
    s = clean_string(orig)
    if not s:
        return ""
    # 辞書完全一致
    if s in mapping:
        return mapping[s]
    # ファジーマッチ
    cand, score, _ = process.extractOne(s, mapping.keys(), scorer=fuzz.token_set_ratio)
    if score >= 90:
        return mapping[cand]
    # API補完
    prompt = f"この{field_name}を業務上の標準表記にしてください：{s}"
    std = call_chatgpt(prompt, field_name)
    if std:
        try:
            with open(dict_path, 'a', encoding='utf-8', newline='') as f:
                f.write(f"{s},{std}\n")
            mapping[s] = std
            return std
        except:
            pass
    # ログに記録
    log_unmatched(f"{field_name}未正規化", orig)
    return ""

# ─── 抽出ロジック ───

def extract_items(df: pd.DataFrame, meta: dict) -> list[dict]:
    # 各種マップをロード
    comp_map     = load_mapping_dict(COMPANY_DICT_PATH)
    store_map    = load_mapping_dict(STORE_DICT_PATH)
    store_map    |= load_mapping_dict(STORE_MAPPING_PATH)
    client_map   = load_mapping_dict(CLIENT_DICT_PATH)
    customer_map = load_mapping_dict(CUSTOMER_DICT_PATH)
    shipto_map   = load_mapping_dict(SHIPTO_DICT_PATH)

    recs = []
    for idx, row in df.iterrows():
        # 金額必須
        if pd.isna(row.get('金額')):
            continue

        # 日付補完（NaT → API推定 → 空欄 or yyyy/MM/dd）
        dt = row.get('日付')
        if pd.isna(dt):
            rec_dict = row.to_dict()
            prompt = (
                "以下のレコード全体を参考に、YYYY/MM/DD 形式で日付を１つだけ返してください。\n"
                f"{rec_dict}"
            )
            resp = call_chatgpt(prompt, "日付推定")
            try:
                dt_parsed = pd.to_datetime(resp, format='%Y/%m/%d', errors='coerce')
            except:
                dt_parsed = pd.NaT
            if pd.isna(dt_parsed):
                date_str = ""
                log_unmatched("日付推定失敗", f"{meta.get('filepath')}#行{idx} → {resp}")
            else:
                date_str = dt_parsed.strftime('%Y/%m/%d')
                # ヘッダー揺れ元が分かれば辞書に追加しても良い
        else:
            date_str = dt.strftime('%Y/%m/%d')

        # 名寄せ対象フィールド
        company   = normalize_field(str(row.get('企業','')),   comp_map,     COMPANY_DICT_PATH, "企業名")
        store     = normalize_field(str(row.get('店舗','')),   store_map,    STORE_DICT_PATH,   "店舗名")
        client    = normalize_field(str(row.get('ご依頼主','')), client_map,  CLIENT_DICT_PATH, "ご依頼主")
        customer  = normalize_field(str(row.get('お客様名','')), customer_map,CUSTOMER_DICT_PATH,"お客様名")
        shipto    = normalize_field(str(row.get('発送先名','')), shipto_map,  SHIPTO_DICT_PATH, "発送先名")

        # 抽出対象：商品名・作業項目
        prod = clean_string(row.get('商品名',''))
        work = clean_string(row.get('作業項目',''))

        recs.append({
            '部署':     meta['部署'],
            '元請け':   meta['元請け'],
            '日付':     date_str,
            '分類':     row.get('分類','不明'),
            '企業名':   company,
            '店舗名':   store,
            'ご依頼主': client,
            'お客様名': customer,
            '発送先名': shipto,
            '商品名':   prod,
            '作業項目': work,
            '数量':     row.get('数量',0),
            '単価':     row.get('単価',0),
            '金額':     row.get('金額',0)
        })
    return recs

# ─── メイン処理 ───

def handle_new_file(filepath: str) -> None:
    meta = parse_filename(filepath)
    if 'エラー' in meta:
        log_unmatched('ファイル名', filepath)
        return
    ym = meta['年月']
    print(f"[REGEN] 全社再生成開始: 年月={ym}")

    # 1) ファイル収集
    candidates = []
    for base in (WATCH_DIR, PROCESSED_DIR):
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(VALID_EXTENSIONS): continue
                m = parse_filename(fn)
                if 'エラー' in m or m.get('年月')!=ym: continue
                candidates.append((os.path.join(root,fn), m))
    print(f"[DEBUG] 対象ファイル数: {len(candidates)}")

    all_records = []
    for path, meta in candidates:
        try:
            # 読み込み
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path)
            else:
                sheets = pd.read_excel(path, sheet_name=None)
                df = pd.concat([normalize_columns(s) for s in sheets.values()], ignore_index=True)
            df = normalize_columns(df)
            # 日付型
            if '日付' in df.columns:
                df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
            else:
                log_unmatched('列','日付が存在しません')
            meta['filepath'] = path
            all_records.extend(extract_items(df, meta))
            # アーカイブ
            from watch_folder import archive_file
            archive_file(path, success=True)
        except Exception as e:
            log_unmatched('読込エラー', f"{path}: {e}")
            from watch_folder import archive_file
            archive_file(path, success=False)

    if not all_records:
        print("[ERROR] 処理可能なレコードがありません")
        return

    df_final = pd.DataFrame(all_records)
    print(f"[EXTRACT] 総レコード数: {len(df_final)}")

    # 列幅指定
    col_widths = {
        '部署':8,'元請け':20,'日付':20,'分類':8,
        '企業名':20,'店舗名':45,'ご依頼主':20,'お客様名':20,'発送先名':20,
        '商品名':55,'作業項目':55,'数量':8,'単価':15,'金額':20
    }

    # 部署別出力
    for dept, grp in df_final.groupby('部署'):
        out = os.path.join(OUTPUT_DIR, dept); os.makedirs(out, exist_ok=True)
        base = f"{ym}_records"
        csv_p  = os.path.join(out, f"{dept}_{base}.csv")
        xlsx_p = os.path.join(out, f"{dept}_{base}.xlsx")
        grp.to_csv(csv_p, index=False, encoding='utf-8-sig')
        with pd.ExcelWriter(xlsx_p, engine='xlsxwriter') as w:
            grp.to_excel(w, index=False, sheet_name='Sheet1')
            ws = w.sheets['Sheet1']
            for i,col in enumerate(grp.columns):
                ws.set_column(i,i,col_widths.get(col,15))

    # 全社統合
    all_out = os.path.join(OUTPUT_DIR,'_全社統合'); os.makedirs(all_out, exist_ok=True)
    csv_a  = os.path.join(all_out, f"全社統合_{ym}_records.csv")
    xlsx_a = os.path.join(all_out, f"全社統合_{ym}_records.xlsx")
    df_final.to_csv(csv_a, index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(xlsx_a, engine='xlsxwriter') as w:
        df_final.to_excel(w, index=False, sheet_name='Sheet1')
        ws = w.sheets['Sheet1']
        for i,col in enumerate(df_final.columns):
            ws.set_column(i,i,col_widths.get(col,15))

    print(f"[DONE] 全社再生成完了: {ym}")
