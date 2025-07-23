#processor.py 
import os 
import re
import unicodedata
import pandas as pd
import csv
from datetime import datetime
import openai
from typing import List

openai.api_key = os.getenv("OPENAI_API_KEY")

def call_chatgpt_api(prompt: str,
                     model: str = "gpt-3.5-turbo",
                     temperature: float = 0.0,
                     max_tokens: int = 50) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    # 1) テストモード：キーがない場合は候補返却（既存挙動）
    if not api_key:
        m = re.search(r'候補: \["(.+)"\]', prompt)
        return m.group(1) if m else ""

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system",  "content": "あなたは正規化アシスタントです。"},
                {"role": "user",    "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            n=1,
        )
        return response.choices[0].message.content.strip()
    except openai.error.APIConnectionError as e:
        log_unmatched('ChatGPT APIエラー', f"接続エラー: {e}")
    except openai.error.RateLimitError as e:
        log_unmatched('ChatGPT APIエラー', f"レート制限: {e}")
    except openai.error.InvalidRequestError as e:
        log_unmatched('ChatGPT APIエラー', f"無効なリクエスト: {e}")
    except openai.error.OpenAIError as e:
        log_unmatched('ChatGPT APIエラー', f"サーバーエラー: {e}")

    # 何らかのエラーが起きた場合はフォールバック
    m = re.search(r'候補: \["(.+)"\]', prompt)
    return m.group(1) if m else ""
_mapping_store: dict[str, str] = {}

def load_mapping_store() -> dict[str, str]:
    global _mapping_store
    if not _mapping_store and os.path.exists(MAPPING_STORE_PATH):
        with open(MAPPING_STORE_PATH, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                _mapping_store[row['cleaned']] = row['normalized']
    return _mapping_store

def append_mapping(cleaned: str, normalized: str, field_name: str):
    header = not os.path.exists(MAPPING_STORE_PATH)
    with open(MAPPING_STORE_PATH, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        if header:
            w.writerow(['cleaned','normalized','field_name','created_at'])
        w.writerow([cleaned, normalized, field_name, datetime.utcnow().isoformat()])
    

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
        fn = os.path.basename(fp)
        name, _ = os.path.splitext(fn)
    # 末尾の「_WEB」除去などの処理はそのまま
        parts = name.split('_')
    # 最低 3 要素（部署, 元請け, 年月）があれば OK、4 つ目以降は無視する
        if len(parts) >= 3:
           dept, contractor, ym_jp = parts[0], parts[1], parts[2]
        # 以下は変更なし
        try:
            y, m = re.match(r'(\d{4})年(\d{1,2})月', ym_jp).groups()
            ym = f"{y}-{int(m):02d}"
            return {'filepath': fp, '部署': dept, '下請け': contractor, '年月': ym}
        except Exception:
            pass
        return {'filepath': fp, 'エラー': 'ファイル名パース失敗'}

try:
    from config import (
        VALID_EXTENSIONS,
        WATCH_DIR, PROCESSED_DIR, OUTPUT_DIR,
        COLUMN_ALIASES, MAPPING_STORE_PATH  
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
# ─── フィールド正規化（名寄せ） ───
def normalize_field(orig: str, mapping: dict, dict_path: str, field_name: str) -> str:
    # 1) 前処理済みテキストをキー化
    cleaned = clean_string(orig)
    # 2) 辞書参照
    store = load_mapping_store()
    if cleaned in store:
        return store[cleaned]
    # 3) ChatGPT補完（仮の呼び出し例）
    prompt = (
        f"以下は「{field_name}」の表記ゆれ例です。\n"
        f"– 候補: [\"{cleaned}\"]\n"
        "正式名称を一つだけ日本語で返してください。"
    )
    response = call_chatgpt_api(prompt)
    normalized = response.strip()

    # 6) API自体は成功しても「そのまま返し」や空文字なら名寄せ失敗扱い
    if not normalized or normalized == cleaned:
        log_unmatched(
            '名寄せ失敗',
            f"{field_name}: 候補={cleaned} → 正式名称取得失敗"
        )
        return cleaned

    # 4) 辞書追加
    if normalized and normalized != cleaned:
        append_mapping(cleaned, normalized, field_name)
        store[cleaned] = normalized

    # 5) フォールバック
    return normalized or cleaned


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
    '売上','売り上げ','金額','合計額','total','amount',
    '売上高','sales','revenue',
    '請求金額','ご請求金額','請求額',
    '作業金額','工賃',
    '手数料','commission','handling_fee',
    '運賃','送料','freight','shipping'
]
AMOUNT_PATTERN = re.compile(r'.*費$')

def is_amount_header(hdr: str) -> bool:
    h = normalize_header(hdr)
    # 1) 「売上」「売り上げ」で完全一致
    if h in ('売上', '売り上げ'):
        return True
    # 2) それ以外はキーワード部分一致 or 「～費」で終わるパターン
    return any(kw in h for kw in AMOUNT_KEYWORDS) or bool(AMOUNT_PATTERN.match(h))
# ─── 列名正規化 ───
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    already_mapped: set[str] = set()

    # 優先度の高い列名からチェックするために、aliases を順序付きで扱う
    for std_col, aliases in COLUMN_ALIASES.items():
        norm_aliases = [normalize_header(a) for a in aliases]
        # 明示的に「完全一致を優先」、その後に「部分一致」
        for orig in df.columns:
            norm_orig = normalize_header(orig)

            # 完全一致
            if norm_orig in norm_aliases and std_col not in already_mapped:
                rename_map[orig] = std_col
                already_mapped.add(std_col)

        for orig in df.columns:
            norm_orig = normalize_header(orig)
            # 部分一致（あいまいマッチ） ← 完全一致がすでにされていたらスキップ
            if any(alias in norm_orig for alias in norm_aliases) and std_col not in already_mapped:
                rename_map[orig] = std_col
                already_mapped.add(std_col)

    return df.rename(columns=rename_map)



# ─── 動的ヘッダ検出付き読み込み ───
def read_with_dynamic_header(path: str) -> dict[str, pd.DataFrame]:
    # 1) 全シートを一括でヘッダーなし読み込み
    print(f"[DEBUG] → read_with_dynamic_header start: path={path}")
    all_preview: dict[str, pd.DataFrame] = pd.read_excel(
        path, sheet_name=None, header=None, nrows=5
    )
    sheet_dfs: dict[str, pd.DataFrame] = {}
    base = os.path.splitext(os.path.basename(path))[0]

    # 2) 各シートを順に処理
    for sheet, preview in all_preview.items():
        print(f"[DEBUG] → processing sheet: {sheet}, preview shape={preview.shape}")
        key = f"{base}_{sheet}"

        # ヘッダー行の候補検出（プレビュー5行目まで）
        header_row = 0
        for i, row in preview.iterrows():
            print(f"[DEBUG]   row[{i}] type={type(row)}, values={row.values[:5]}")
            norm = [normalize_header(str(v)) for v in row.fillna('')]
            if any(is_amount_header(h) or '金額' in h for h in norm):
                header_row = i
                break
        print(f"[DEBUG] → detected header_row={header_row} for sheet {sheet}")
        df = pd.read_excel(path, sheet_name=sheet, header=header_row)
        if df.empty:
            log_unmatched('読込エラー', f"{base}_{sheet}: 空のシートです")
            continue
        df['__source'] = f"{base}_{sheet}"
        sheet_dfs[sheet] = df


    # 3) 全シート読み込み後のチェック（ここはループの外）
    if not sheet_dfs:
        raise ValueError(f"{base} のシートすべてでデータが取れませんでした")
    return sheet_dfs

    # 4) 正常シートを縦結合して返す
    return pd.concat(dfs, ignore_index=True, sort=False)

def parse_flexible_date(raw_date, year_hint: str) -> str:
    if pd.isna(raw_date):
        return ''
    s = str(raw_date).strip()

    # 1) 「1月9日」「12月31日」
    m = re.match(r'^(\d{1,2})月(\d{1,2})日$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    # 2) 「1/9」「12/31」「1-9」
    m = re.match(r'^(\d{1,2})[\/\-](\d{1,2})$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    # 3) 「1月9」「12月31」
    m = re.match(r'^(\d{1,2})月(\d{1,2})$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    # 4) 「20240109」 ← ここを追加！！
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s)
    if m:
        y, m_, d = map(int, m.groups())
        return f"{y}/{m_:02d}/{d:02d}"

    # 5) 「2024年1月9日」
    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', s)
    if m:
        y, m_, d = map(int, m.groups())
        return f"{y}/{m_:02d}/{d:02d}"

    # 6) fallback: pandas にまかせる
    try:
        dt = pd.to_datetime(s, errors='coerce')
        if not pd.isna(dt):
            return dt.strftime('%Y/%m/%d')
    except:
        pass

    return ''

def normalize(col: str) -> str:
    s = col.lower()
    s = s.translate(str.maketrans({'　':' ', '（':'(', '）':')'}))
    s = re.sub(r'[^\w\s]', '', s)
    s = s.replace(' ', '')
    for honorific in ['様','さん','殿','先生','御中']:
        s = s.replace(honorific, '')
    return s

def pick_store_column(row: pd.Series, raw_cols: List[str]) -> str:
    # 正規化済みカラム名リスト
    norm_map = {normalize(c): c for c in raw_cols}
    norm_cols = list(norm_map.keys())

    # マッチング用パターン
    patterns = [
        r'^依頼.*',        # 依頼主、依頼者、依頼先...
        r'^ご?依頼.*',     # ご依頼主、ご依頼人...
        r'^お客様.*',      # お客様、お客様名...
        r'顧客.*',         # 顧客、顧客名...
        r'(クライアント)',  # 得意先、クライアント
        r'(送|発|配)送.*先',  # 送り先、発送先、配送先
        r'宛先',           # 宛先
        r'店舗.*',         # 店舗、店舗名
        r'ショップ.*',     # ショップ、ショップ名
    ]

    # 1) パターンマッチ最優先
    for pat in patterns:
        regex = re.compile(pat)
        for nc in norm_cols:
            if regex.search(nc):
                orig = norm_map[nc]
                return str(row.get(orig, ''))

    # 2) 部分一致フォールバック
    for nc, orig in norm_map.items():
        if any(key in nc for key in ['主','客','先','店']):
            return str(row.get(orig, ''))

    # 3) それでもなければ「店舗」列
    return str(row.get('店舗', ''))


# ─── レコード抽出 ───

def is_summary_row(row: pd.Series) -> bool:
    """
    行中の全セルを文字列化して空白を除去し、
    どれかに「小計」または「合計」を含んでいれば True を返す。
    """
    texts = (
        row
        .astype(str)
        .str.replace(r'\s+', '', regex=True)  # 空白をすべて削除
    )
    return texts.str.contains(r'小計|合計', na=False).any()

def extract_items(df: pd.DataFrame, meta: dict) -> list[dict]:
    # ─── 小計・合計行を除外 ───
    df = df.loc[~df.apply(is_summary_row, axis=1)]
    # 除外後の列一覧を取得
    raw_cols  = list(df.columns)
    norm_cols = [normalize_header(c) for c in raw_cols]
    date_col = next((c for c in raw_cols if normalize_header(c) == '日付'), None)
    if date_col:
     ym = meta['年月']            # "YYYY-MM"
    default_date = f"{ym}-01"
    df[date_col] = df[date_col].fillna('')
    df[date_col] = df[date_col].apply(
        lambda x: parse_flexible_date(x, ym.split('-')[0]) or default_date
    )
    idx_qty  = next((i for i,h in enumerate(norm_cols) if h.endswith('数量')), None)
    idx_unit = next((i for i,h in enumerate(norm_cols) if '単価' in h), None)

    # ── 金額列候補を全部取得 ──
    amt_cands = [c for c in raw_cols if is_amount_header(c)]
    # ── その中で「合計」っぽい列を絞り込む（部分一致） ──
    total_cands = [
        c for c in amt_cands
        if '合計' in normalize_header(c) or 'total' in normalize_header(c)
    ]

    # ── 合計列優先 ──
    if total_cands:
        # 複数なら、列ごとの合計値が最大のものを選択
        sums = {
            c: df[c].map(lambda x: try_parse(x) or 0).sum()
            for c in total_cands
        }
        chosen = max(sums, key=sums.get)
        idx_amount = raw_cols.index(chosen)
    elif amt_cands:
        # 合計列がなければ最初の候補
        idx_amount = raw_cols.index(amt_cands[0])
    else:
        log_unmatched('列検出エラー', f"{meta['filepath']}: 金額列が見つかりません")
        return []

    recs: list[dict] = []
    for row_i, row in df.iterrows():
        raw_date   = row.get('日付')
        year_hint  = meta.get('年月', '').split('-')[0]
        date_str   = parse_flexible_date(raw_date, year_hint)
        if not date_str:
            log_unmatched(
                '日付抽出失敗',
                f"{meta['filepath']}#行{row_i}: 元値={raw_date}"
            )
            continue

        # 数量
        if idx_qty is None or df.iloc[:, idx_qty].isna().all():
            q = 1
        else:
            q = try_parse(row.iloc[idx_qty])

        # 単価（通常どおり）
        p = try_parse(row.iloc[idx_unit]) if idx_unit is not None else None
        if p is not None:
            p = round(p, 1)

        # 金額（選択された1列のみ）
        a = try_parse(row.iloc[idx_amount])
        if a is None:
            log_unmatched(
                '金額欠損',
                f"{meta['filepath']}#行{row_i}: 列={raw_cols[idx_amount]}, 値={row.iloc[idx_amount]}"
            )
            continue

        raw_store = pick_store_column(row, raw_cols)
        store     = normalize_field(raw_store, {}, MAPPING_STORE_PATH, '店舗名')
        item      = clean_string(row.get('作業項目/商品名', ''))

        recs.append({
            '部署':             meta.get('部署',''),
            '下請け':           meta.get('下請け',''),
            '日付':             date_str,
            '店舗名':           store,
            '作業項目/商品名':  item,
            '数量':             q,
            '単価':             p,
            '金額':             a
        })

    return recs

def filter_duplicates_by_basename(file_paths: list[str]) -> set[str]:
    """
    同一 basename をもつファイルが複数ある場合、
    更新日時最新の１件だけ残し、その basename の最新パスを返す。
    """
    groups: dict[str, list[str]] = {}
    for p in file_paths:
        bn = os.path.basename(p)
        groups.setdefault(bn, []).append(p)

    kept: set[str] = set()
    for bn, paths in groups.items():
        # 単一ならそのまま
        if len(paths) == 1:
            kept.add(paths[0])
        else:
            # 更新日時最新を選択
            latest = max(paths, key=lambda x: os.path.getmtime(x))
            kept.add(latest)
            for other in paths:
                if other != latest:
                    log_unmatched(
                        '重複ファイル',
                        f"{other} は {latest} と同名のためスキップ"
                    )
    return kept

# ─── メイン処理 ───
def handle_new_file(filepath: str) -> None:
    from watch_folder import archive_file  # アーカイブ用

    # ① ファイル名パース
    meta = parse_filename(filepath)
    if 'エラー' in meta:
        log_unmatched('ファイル名', filepath)
        return

    # ② 対象年月・対象年
    ym   = meta['年月']             # e.g. "2025-02"
    year = ym.split('-')[0]         # e.g. "2025"
    print(f"[REGEN] 全社再生成開始: 年月={ym}")

    # ③ 候補ファイル収集（WATCH_DIR + PROCESSED_DIR）
    candidates_month: list[tuple[str, dict]] = []
    candidates_year:  list[tuple[str, dict]] = []
    for base in (WATCH_DIR, PROCESSED_DIR):
        for root, _, files in os.walk(base):
            for fn in files:
                fullpath = os.path.join(root, fn)
                m = parse_filename(fullpath)
                if 'エラー' in m:
                    continue
                if m.get('年月') == ym:
                    candidates_month.append((fullpath, m))
                if m.get('年月', '').split('-',1)[0] == year:
                    candidates_year.append((fullpath, m))

    # ④ 月次：basename 重複排除 → 抽出 → アーカイブ
    month_paths = [p for p, _ in candidates_month]
    kept_month = set(filter_duplicates_by_basename(month_paths))
    all_records_month: list[dict] = []

    for path, m in candidates_month:
        if path not in kept_month:
            continue
        m['filepath'] = path

        # ── シート単位で DataFrame dict を取得 ──
        try:
            if path.lower().endswith('.csv'):
                # CSV はファイル名をシート名とみなす
                base = os.path.splitext(os.path.basename(path))[0]
                sheets = { base: pd.read_csv(path) }
            else:
                # Excel は複数シートを dict で返すように read_with_dynamic_header を修正済み
                sheets = read_with_dynamic_header(path)
        except Exception as e:
            print(f"[ERROR] read_with_dynamic_header failed: {repr(e)}")
            raise

        # ── 各シートを個別処理 ──
        for sheet_name, df in sheets.items():
            print(f"[DEBUG2] sheet={sheet_name}, rows={len(df)}, cols={df.columns.tolist()}")

            # ② 列名正規化
            try:
                df2 = normalize_columns(df)
            except Exception as e:
                print(f"[ERROR] normalize_columns failed: {repr(e)}")
                raise
            print(f"[DEBUG2] after normalize_columns ({sheet_name}), cols={df2.columns.tolist()}")

            # ③ レコード抽出
            try:
                # シート名をメタに追加しておく
                m_sheet = m.copy()
                m_sheet['sheet'] = sheet_name
                recs = extract_items(df2, m_sheet)
            except Exception as e:
                print(f"[ERROR] extract_items failed ({sheet_name}): {repr(e)}")
                raise
            print(f"[DEBUG2] extract_items returned {len(recs)} records for sheet {sheet_name}")

            all_records_month.extend(recs)

        # ── 元ファイル単位でアーカイブ ──
        archive_file(path, success=True)

    # ── 最終的に全シート分を結合 ──
    df_month = pd.DataFrame(all_records_month)
    print(f"[EXTRACT-MONTH] 総レコード数: {len(df_month)} 件")

    # ─── ⑤ 年次：移動済みパス補正 → basename 重複排除 → 抽出（アーカイブあり） ───
    corrected = []
    for path, m in candidates_year:
        if not os.path.exists(path):
            alt = os.path.join(PROCESSED_DIR, m['部署'], os.path.basename(path))
            if os.path.exists(alt):
                path = alt
        corrected.append((path, m))

    year_paths = [p for p, _ in corrected]
    kept_year = set(filter_duplicates_by_basename(year_paths))
    all_records_year: list[dict] = []

    for path, m in corrected:
        if path not in kept_year:
            continue
        m['filepath'] = path

        try:
            # ── シートごとに dict を取得 ──
            if path.lower().endswith('.csv'):
                base = os.path.splitext(os.path.basename(path))[0]
                sheets = { base: pd.read_csv(path) }
            else:
                sheets = read_with_dynamic_header(path)

            # ── 各シートを個別処理 ──
            for sheet_name, df in sheets.items():
                print(f"[DEBUG] year sheet={sheet_name}, rows={len(df)}, cols={df.columns.tolist()}")

                # 列名正規化
                df.columns = [normalize_header(c) for c in df.columns]
                df2 = normalize_columns(df)

                # メタにシート名を追加
                m_sheet = m.copy()
                m_sheet['sheet'] = sheet_name
                recs = extract_items(df2, m_sheet)
                print(f"[DEBUG] extract_items returned {len(recs)} records for sheet {sheet_name}")

                all_records_year.extend(recs)

            # 全シート正常終了なら success=True
            archive_file(path, success=True)

        except Exception as e:
            log_unmatched('読込エラー', f"{path}: {e}")
            archive_file(path, success=False)

    df_year = pd.DataFrame(all_records_year)
    print(f"[EXTRACT-YEAR] 総レコード数: {len(df_year)} 件")


    # ⑥ 出力設定（列幅マップ）
    col_widths = {
        '部署': 8, '下請け': 20, '日付': 20,
        '店舗名': 45, '作業項目/商品名': 60,
        '数量': 8, '単価': 15, '金額': 20
    }

    # ⑥-1) 月次部署別出力
    base_month = f"{ym}_records"
    for dept, grp in df_month.groupby('部署'):
        out_dir = os.path.join(OUTPUT_DIR, dept)
        os.makedirs(out_dir, exist_ok=True)
        subs = grp.groupby('下請け', as_index=False)[['数量','金額']].sum()
        subs['作業項目/商品名'] = '小計'
        total = {
            '部署': dept, '下請け': '', '日付': '',
            '店舗名': '', '作業項目/商品名': '合計',
            '数量': grp['数量'].sum(), '単価': '', '金額': grp['金額'].sum()
        }
        grp_ext = pd.concat([grp, subs, pd.DataFrame([total])], ignore_index=True)

        grp_ext.to_csv(
            os.path.join(out_dir, f"{dept}_{base_month}.csv"),
            index=False, encoding='utf-8-sig'
        )
        with pd.ExcelWriter(
            os.path.join(out_dir, f"{dept}_{base_month}.xlsx"),
            engine='xlsxwriter'
        ) as w:
            grp_ext.to_excel(w, index=False, sheet_name='Sheet1')
            ws, wb = w.sheets['Sheet1'], w.book
            fmt = wb.add_format({'num_format':'#,##0'})
            for i, col in enumerate(grp_ext.columns):
                ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
            ws.autofilter(0, 0, len(grp_ext), len(grp_ext.columns)-1)

    # ⑥-2) 月次全社統合出力
    all_mon = os.path.join(OUTPUT_DIR, '_全社統合')
    os.makedirs(all_mon, exist_ok=True)
    subs_c = df_month.groupby('下請け',   as_index=False)[['数量','金額']].sum().assign(
        部署='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名':'会社小計'}
    )
    subs_d = df_month.groupby('部署',    as_index=False)[['数量','金額']].sum().assign(
        下請け='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名':'部署小計'}
    )
    total_all = {
        '部署':'','下請け':'','日付':'',
        '店舗名':'','作業項目/商品名':'全社合計',
        '数量': df_month['数量'].sum(), '単価':'', '金額': df_month['金額'].sum()
    }
    df_ext = pd.concat([df_month, subs_c, subs_d, pd.DataFrame([total_all])], ignore_index=True)

    df_ext.to_csv(
        os.path.join(all_mon, f"全社統合_{ym}_records.csv"),
        index=False, encoding='utf-8-sig'
    )
    with pd.ExcelWriter(
        os.path.join(all_mon, f"全社統合_{ym}_records.xlsx"),
        engine='xlsxwriter'
    ) as w:
        df_ext.to_excel(w, index=False, sheet_name='Sheet1')
        ws, wb = w.sheets['Sheet1'], w.book
        fmt = wb.add_format({'num_format':'#,##0'})
        for i, col in enumerate(df_ext.columns):
            ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
        ws.autofilter(0, 0, len(df_ext), len(df_ext.columns)-1)

    # ⑥-3) 年次部署別出力
    for dept, grp in df_year.groupby('部署'):
        year_dir = os.path.join(OUTPUT_DIR, dept, 'yearly')
        os.makedirs(year_dir, exist_ok=True)
        base_year = f"{dept}_{year}_records"
        subs = grp.groupby('下請け', as_index=False)[['数量','金額']].sum()
        subs['作業項目/商品名'] = '部署小計'
        total = {
            '部署': dept, '下請け': '', '日付': '',
            '店舗名': '', '作業項目/商品名':'年次合計',
            '数量': grp['数量'].sum(), '単価': '', '金額': grp['金額'].sum()
        }
        grp_ext = pd.concat([grp, subs, pd.DataFrame([total])], ignore_index=True)

        grp_ext.to_csv(
            os.path.join(year_dir, f"{base_year}.csv"),
            index=False, encoding='utf-8-sig'
        )
        with pd.ExcelWriter(
            os.path.join(year_dir, f"{base_year}.xlsx"),
            engine='xlsxwriter'
        ) as w:
            grp_ext.to_excel(w, index=False, sheet_name='Sheet1')
            ws, wb = w.sheets['Sheet1'], w.book
            fmt = wb.add_format({'num_format':'#,##0'})
            for i, col in enumerate(grp_ext.columns):
                ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
            ws.autofilter(0, 0, len(grp_ext), len(grp_ext.columns)-1)

    # ⑥-4) 年次全社統合出力
    company_year_dir = os.path.join(OUTPUT_DIR, '_全社統合', 'yearly')
    os.makedirs(company_year_dir, exist_ok=True)
    subs_cy = df_year.groupby('下請け', as_index=False)[['数量','金額']].sum().assign(
        部署='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名':'会社小計'}
    )
    subs_dy = df_year.groupby('部署',    as_index=False)[['数量','金額']].sum().assign(
        下請け='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名':'部署小計'}
    )
    total_yr = {
        '部署':'','下請け':'','日付':'',
        '店舗名':'','作業項目/商品名':'年次合計',
        '数量': df_year['数量'].sum(), '単価':'', '金額': df_year['金額'].sum()
    }
    df_yr_ext = pd.concat([df_year, subs_cy, subs_dy, pd.DataFrame([total_yr])], ignore_index=True)

    df_yr_ext.to_csv(
        os.path.join(company_year_dir, f"全社統合_{year}_records.csv"),
        index=False, encoding='utf-8-sig'
    )
    with pd.ExcelWriter(
        os.path.join(company_year_dir, f"全社統合_{year}_records.xlsx"),
        engine='xlsxwriter'
    ) as w:
        df_yr_ext.to_excel(w, index=False, sheet_name='Sheet1')
        ws, wb = w.sheets['Sheet1'], w.book
        fmt = wb.add_format({'num_format':'#,##0'})
        for i, col in enumerate(df_yr_ext.columns):
            ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
        ws.autofilter(0, 0, len(df_yr_ext), len(df_yr_ext.columns)-1)

    print(f"[DONE] 全社再生成完了: 年月={ym}／年次完了")