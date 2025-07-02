import os
import re
import unicodedata
import pandas as pd

# ─── 外部ユーティリティ／設定読み込み ───
try:
    from logger import log_unmatched
except ImportError:
    def log_unmatched(tag: str, message: str):
        print(f"[UNMATCHED][{tag}] {message}")

try:
    from parser import parse_filename
except ImportError:
    def parse_filename(fp: str) -> dict:
        # filepath, 部署, 元請け, 年月 の最低限を返す
        return {'filepath': fp, '部署': '', '元請け': '', '年月': ''}

try:
    from config import (
        VALID_EXTENSIONS,
        WATCH_DIR, PROCESSED_DIR, OUTPUT_DIR,
        COLUMN_ALIASES
    )
except ImportError:
    # テスト用ダミー設定
    VALID_EXTENSIONS = ('.csv', '.xlsx', '.xls')
    WATCH_DIR       = 'watch'
    PROCESSED_DIR   = 'processed'
    OUTPUT_DIR      = 'output'
    COLUMN_ALIASES = {
        '作業項目/商品名': [
            '作業内容', 'サービス項目', '作業項目',
            '商品', '品名', '内容', '商品名'
        ]
    }

# ─── 文字列クリーニング ───
def clean_string(s: str) -> str:
    if not isinstance(s, str):
        return ''
    # Unicode NFKC 正規化
    s = unicodedata.normalize('NFKC', s)
    # 改行をスペースに
    s = s.replace('\n', ' ')
    # 連続空白を 1 スペースに
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# ─── フィールド正規化スタブ ───
def normalize_field(orig: str, mapping: dict, dict_path: str, field_name: str) -> str:
    # ここでマッピング辞書やChatGPT補完ロジックを呼び出せます
    return orig or ''

# ─── ヘッダ正規化強化 ───
def normalize_header(h: str) -> str:
    """
    ・Unicode NFKC正規化
    ・改行・全角/半角スペースを削除
    ・小文字化
    """
    if not isinstance(h, str):
        return ''
    s = unicodedata.normalize('NFKC', h)
    # 改行除去 & 全角／半角スペースをまとめて削除
    s = re.sub(r'\s+', '', s)
    return s.lower()

# ─── 数値正規化＆パース ───
def normalize_numeric_text(s) -> str:
    if pd.isna(s):
        return ''
    text = str(s)
    z2h = str.maketrans('０１２３４５６７８９．，', '0123456789.,')
    text = text.translate(z2h)
    text = re.sub(r'[¥￥円,]', '', text)
    return text.strip()

def try_parse(s) -> float | None:
    try:
        num = normalize_numeric_text(s)
        return float(num) if num != '' else None
    except:
        return None

# ─── 金額列判定 ───
AMOUNT_KEYWORDS = [
    '金額','合計額','total','amount',
    '売上高','sales','revenue',
    '請求金額','ご請求金額','請求額',
    '作業金額','工賃',
    '手数料','commission','handling_fee',
    '運賃','送料','freight','shipping'
]
AMOUNT_PATTERN = re.compile(r'.*費$')

def is_amount_header(hdr: str) -> bool:
    h = normalize_header(hdr)
    return any(kw in h for kw in AMOUNT_KEYWORDS) or bool(AMOUNT_PATTERN.match(h))

# ─── 列名正規化 ───
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for std_col, aliases in COLUMN_ALIASES.items():
        norm_aliases = [normalize_header(a) for a in aliases]
        for orig in df.columns:
            norm_orig = normalize_header(orig)
            if any(alias in norm_orig for alias in norm_aliases):
                rename_map[orig] = std_col
    return df.rename(columns=rename_map)

# ─── 動的ヘッダ検出付き読み込み ───
def read_with_dynamic_header(path: str) -> pd.DataFrame:
    """
    通常 header=0 で読み込み、Unnamed が多ければ header=1 で再読み込みする
    """
    # まず header=0 で試す
    sheets0 = pd.read_excel(path, sheet_name=None, header=0)
    df0 = pd.concat(sheets0.values(), ignore_index=True)
    cols0 = list(df0.columns)
    unnamed_count = sum(1 for c in cols0 if str(c).startswith("Unnamed"))
    # Unnamed が半分以上なら header=1
    if unnamed_count >= len(cols0) * 0.5:
        sheets1 = pd.read_excel(path, sheet_name=None, header=1)
        return pd.concat(sheets1.values(), ignore_index=True)
    else:
        return df0

# ─── レコード抽出 ───
def extract_items(df: pd.DataFrame, meta: dict) -> list[dict]:
    raw_cols  = list(df.columns)
    norm_cols = [normalize_header(c) for c in raw_cols]

    idx_qty    = next((i for i,h in enumerate(norm_cols) if '数量' in h), None)
    idx_unit   = next((i for i,h in enumerate(norm_cols) if '単価' in h), None)
    idx_amount = next((i for i,c in enumerate(raw_cols) if is_amount_header(c)), None)

    if idx_amount is None:
        log_unmatched('列検出エラー', f"{meta['filepath']}: 金額列が見つかりません")
        return []

    recs: list[dict] = []
    for row_i, row in df.iterrows():
        raw_date = row.get('日付')
        if pd.isna(raw_date):
            date_str = ''
        else:
            dt = pd.to_datetime(raw_date, errors='coerce')
            date_str = dt.strftime('%Y/%m/%d') if not pd.isna(dt) else ''

        q = try_parse(row.iloc[idx_qty])  if idx_qty  is not None else None
        p = try_parse(row.iloc[idx_unit]) if idx_unit is not None else None
        a = try_parse(row.iloc[idx_amount])

        if a is None:
            log_unmatched(
                '金額欠損',
                f"{meta['filepath']}#行{row_i}: 列={raw_cols[idx_amount]}, 値={row.iloc[idx_amount]}"
            )
            continue

        if q is not None and p is not None and pd.isna(row.iloc[idx_amount]):
            a = q * p
        if q is not None and a is not None and p is None:
            p = a / q if q else None
        if p is not None and a is not None and q is None:
            q = a / p if p else None
        if None not in (q, p, a) and abs(q * p - a) / max(a, 1) > 0.01:
            log_unmatched(
                '不整合',
                f"{meta['filepath']}#行{row_i}: {q}×{p} ≠ {a}"
            )

        company = normalize_field(str(row.get('企業','')), {}, '', '企業名')
        store   = normalize_field(str(row.get('店舗','')), {}, '', '店舗名')
        item    = clean_string(row.get('作業項目/商品名', ''))

        recs.append({
            '部署':             meta.get('部署',''),
            '元請け':           meta.get('元請け',''),
            '日付':             date_str,
            '企業名':           company,
            '店舗名':           store,
            '作業項目/商品名':  item,
            '数量':             q,
            '単価':             p,
            '金額':             a
        })

    return recs

# ─── メイン処理 ───
def handle_new_file(filepath: str) -> None:
    meta = parse_filename(filepath)
    if 'エラー' in meta:
        log_unmatched('ファイル名', filepath)
        return

    ym   = meta['年月']
    year = ym.split('-')[0]
    print(f"[REGEN] 全社再生成開始: 年月={ym}")

    # 1) 対象ファイル収集
    candidates: list[tuple[str, dict]] = []
    for base in (WATCH_DIR, PROCESSED_DIR):
        for root, _, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(VALID_EXTENSIONS):
                    continue
                m = parse_filename(fn)
                if 'エラー' in m or m.get('年月') != ym:
                    continue
                candidates.append((os.path.join(root, fn), m))
    print(f"[DEBUG] 対象ファイル数: {len(candidates)}")

    all_records: list[dict] = []
    for path, m in candidates:
        try:
            # データ読み込み
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path)
            else:
                df = read_with_dynamic_header(path)

            # ヘッダ強化正規化＆エイリアスマッチ
            df.columns = [normalize_header(c) for c in df.columns]
            df = normalize_columns(df)

            # 部分一致による強制リネーム（旧ロジック併用）
            keywords = [normalize_header(k) for k in COLUMN_ALIASES.get('作業項目/商品名', [])]
            for orig in list(df.columns):
                if any(kw in orig for kw in keywords):
                    df.rename(columns={orig: '作業項目/商品名'}, inplace=True)
                    break

            # 日付列自動検出
            date_cols = [c for c in df.columns if c.endswith('日')]
            if date_cols:
                for c in date_cols:
                    df[c] = pd.to_datetime(df[c], errors='coerce')
                if '日付' not in df.columns:
                    df = df.rename(columns={date_cols[0]: '日付'})
            else:
                log_unmatched('列検出エラー', f"{path}: 日付列が見つかりません")

            m['filepath'] = path
            extract_list = extract_items(df, m)
            print(f"[DEBUG] {os.path.basename(path)} → {len(extract_list)} 件抽出")
            all_records.extend(extract_list)

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


    # 列幅設定
    col_widths = {
        '部署':8, '元請け':20, '日付':20,
        '企業名':20, '店舗名':45, '作業項目/商品名':60,
        '数量':8, '単価':15, '金額':20
    }

    # ── 月次部署別出力 ──
    for dept, grp in df_final.groupby('部署'):
        out_dir = os.path.join(OUTPUT_DIR, dept)
        os.makedirs(out_dir, exist_ok=True)
        base_month = f"{ym}_records"
        grp.to_csv(os.path.join(out_dir, f"{dept}_{base_month}.csv"),
                   index=False, encoding='utf-8-sig')
        with pd.ExcelWriter(os.path.join(out_dir, f"{dept}_{base_month}.xlsx"),
                            engine='xlsxwriter') as w:
            grp.to_excel(w, index=False, sheet_name='Sheet1')
            ws = w.sheets['Sheet1']
            for i, col in enumerate(grp.columns):
                ws.set_column(i, i, col_widths.get(col, 15))

    # ── 月次全社統合出力 ──
    all_mon = os.path.join(OUTPUT_DIR, '_全社統合')
    os.makedirs(all_mon, exist_ok=True)
    df_final.to_csv(os.path.join(all_mon, f"全社統合_{ym}_records.csv"),
                    index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(os.path.join(all_mon, f"全社統合_{ym}_records.xlsx"),
                        engine='xlsxwriter') as w:
        df_final.to_excel(w, index=False, sheet_name='Sheet1')
        ws = w.sheets['Sheet1']
        for i, col in enumerate(df_final.columns):
            ws.set_column(i, i, col_widths.get(col, 15))

    # ── 年次部署別出力 ──
    for dept, grp in df_final.groupby('部署'):
        year_dir = os.path.join(OUTPUT_DIR, dept, 'yearly')
        os.makedirs(year_dir, exist_ok=True)
        base_year = f"{dept}_{year}_records"
        grp.to_csv(os.path.join(year_dir, f"{base_year}.csv"),
                   index=False, encoding='utf-8-sig')
        with pd.ExcelWriter(os.path.join(year_dir, f"{base_year}.xlsx"),
                            engine='xlsxwriter') as w:
            grp.to_excel(w, index=False, sheet_name='Sheet1')
            ws = w.sheets['Sheet1']
            for i, col in enumerate(grp.columns):
                ws.set_column(i, i, col_widths.get(col, 15))

    # ── 年次全社統合出力 ──
    company_year_dir = os.path.join(OUTPUT_DIR, '_全社統合', 'yearly')
    os.makedirs(company_year_dir, exist_ok=True)
    df_final.to_csv(os.path.join(company_year_dir, f"全社統合_{year}_records.csv"),
                    index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(os.path.join(company_year_dir, f"全社統合_{year}_records.xlsx"),
                        engine='xlsxwriter') as w:
        df_final.to_excel(w, index=False, sheet_name='Sheet1')
        ws = w.sheets['Sheet1']
        for i, col in enumerate(df_final.columns):
            ws.set_column(i, i, col_widths.get(col, 15))

    print(f"[DONE] 全社再生成完了: 年月={ym}／年次完了")

