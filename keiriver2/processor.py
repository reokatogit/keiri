# processor.py
from __future__ import annotations
from pathlib import Path
import csv
import os
import random
import re
import time
import unicodedata
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import difflib
import pandas as pd

# --- OpenAI (任意: 無ければ後で例外にする) ---
try:
    import openai  # noqa: F401
except Exception:
    openai = None  # noqa: F401

# --- ロガー（存在しない場合は安全なフォールバック） ---
try:
    # 新ロガー（提案版）を優先。なければ既存API/printフォールバック
    from logger import notice, caution, error, exception, log_unmatched, log_info
except Exception:
    def notice(msg: str, **kwargs):      print(f"[INFO] {msg} {kwargs if kwargs else ''}")
    def caution(msg: str, **kwargs):     print(f"[WARN] {msg} {kwargs if kwargs else ''}")
    def error(msg: str, **kwargs):       print(f"[ERROR] {msg} {kwargs if kwargs else ''}")
    def exception(msg: str, **kwargs):   print(f"[EXC] {msg} {kwargs if kwargs else ''}")
    def log_unmatched(category: str, value: str, note: str = ""):
        print(f"[UNMATCHED] {category} | {value} | {note}")
    def log_info(message: str):          print(f"[INFO] {message}")

# --- 設定（無ければデフォルト値） ---
try:
    from config import (
        VALID_EXTENSIONS,
        WATCH_DIR, PROCESSED_DIR, OUTPUT_DIR,
        COLUMN_ALIASES, MAPPING_STORE_PATH
    )
except ImportError:
    VALID_EXTENSIONS = ('.csv', '.xlsx', '.xls')
    WATCH_DIR = 'watch'
    PROCESSED_DIR = 'processed'
    OUTPUT_DIR = 'output'
    COLUMN_ALIASES = {
        '作業項目/商品名': [
            '作業内容', 'サービス項目', '作業項目',
            '商品', '品名', '内容', '商品名'
        ]
    }
    MAPPING_STORE_PATH = os.environ.get("MAPPING_STORE_PATH", "mapping_store.csv")

# --- 解析用（無ければ簡易版） ---
try:
    from parser import parse_filename
except ImportError:
    def parse_filename(fp: str) -> dict:
        """
        ファイル名: {部署}_{元請け}_{YYYY年M月}[...].xlsx を想定した簡易パーサ。
        """
        fn = os.path.basename(fp)
        name, _ = os.path.splitext(fn)
        parts = name.split('_')
        if len(parts) >= 3:
            dept, contractor, ym_jp = parts[0], parts[1], parts[2]
            try:
                y, m = re.match(r'(\d{4})年(\d{1,2})月', ym_jp).groups()
                ym = f"{y}-{int(m):02d}"
                return {'filepath': fp, '部署': dept, '下請け': contractor, '年月': ym}
            except Exception:
                pass
        return {'filepath': fp, 'エラー': 'ファイル名パース失敗'}

# --- OpenAI API キー設定（openai がある時だけ） ---
if openai is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")

# =========================
# 名寄せ用 マッピングストア
# =========================
_mapping_store: Dict[str, str] = {}


def load_mapping_store() -> Dict[str, str]:
    """CSV（cleaned, normalized, field_name, created_at）の読み込み。"""
    global _mapping_store
    if not _mapping_store and os.path.exists(MAPPING_STORE_PATH):
        with open(MAPPING_STORE_PATH, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                _mapping_store[row['cleaned']] = row['normalized']
    return _mapping_store


def append_mapping(cleaned: str, normalized: str, field_name: str) -> None:
    """CSV に1行追記。ヘッダがなければ作る。"""
    header_needed = not os.path.exists(MAPPING_STORE_PATH)
    with open(MAPPING_STORE_PATH, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        if header_needed:
            w.writerow(['cleaned', 'normalized', 'field_name', 'created_at'])
        w.writerow([cleaned, normalized, field_name, datetime.utcnow().isoformat()])


# =========================
# 文字列クリーニング
# =========================
FORBIDDEN_CHARS = '「」『』“”‘’()[]{}<>・：；。，、!?？…'
_FORBIDDEN_RE = re.compile(f"[{re.escape(FORBIDDEN_CHARS)}]")


def clean_string(s: str) -> str:
    """
    表記ゆれ正規化用の前処理。各種ダッシュ（- – — ― ─）は残す。
    """
    if not isinstance(s, str):
        return ''
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s)

    # 記号類を削除（ダッシュ類は残す）
    s = re.sub(r'[「」『』“”‘’\(\)\[\]\{\}<>・：；。，、!！\?？…]', '', s)

    # 英数字・日本語以外を削除（ダッシュ類は残す）
    s = re.sub(r'[^\w\u3040-\u30FF\u3400-\u9FFF\-\u2013\u2014\u2015\u2500]', '', s)

    # 敬称・肩書き
    for h in ['様', 'さん', '殿', '先生', '御中', '様分']:
        s = s.replace(h, '')

    # 企業形態表記
    s = re.sub(
        r'(株式会社|（株）|㈱|有限会社|合同会社|LLC|Inc\.?|Co\.?|Ltd\.?)',
        '',
        s,
        flags=re.IGNORECASE
    )
    return s.strip()


# =========================
# 類似度ユーティリティ
# =========================
def _trigrams(s: str) -> List[str]:
    """長さ2以下でも空にならないように 1-gram/2-gram代替。"""
    n = max(1, len(s) - 2)
    return [s[i:i + 3] for i in range(n)]


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(1, len(sa | sb))


def _brand_token(s: str) -> str:
    """先頭のブランドっぽいトークン（例：「くら寿司」「焼肉きんぐ」など）。"""
    for sep in ("店", " ", "　"):
        idx = s.find(sep)
        if idx > 0:
            return s[:idx]
    return s[:min(6, len(s))]


def _similarity(a: str, b: str) -> float:
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    j = _jaccard(_trigrams(a), _trigrams(b))
    bonus = 0.1 if _brand_token(a) == _brand_token(b) else 0.0
    return 0.6 * seq + 0.4 * j + bonus


CAND_THRESHOLD = 0.80  # 0.80以上のみ候補として採用
TOP_K = 3              # 上位3件


def _top_k_similar(cleaned: str, store_keys: Iterable[str]) -> List[Tuple[str, float]]:
    scored = [(key, _similarity(cleaned, key)) for key in store_keys]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:TOP_K]


# =========================
# プロンプト生成
# =========================
def _build_prompt(field_name: str, cleaned: str, candidates: Optional[List[str]]) -> str:
    cand_line = " / ".join(candidates) if candidates else ""
    cand_section = f"【候補】{cand_line}\n" if candidates else ""
    return (
        f"以下は「{field_name}」の店舗名の表記ゆれです。正しい店名を1つだけ返してください。\n\n"
        "【タスク】\n"
        "- 入力の表記ゆれを正し、店舗名を1つに正規化する。\n"
        "- 元の名称に忠実。法人格・部門・「様」「分」「スタッフ」などは除外。\n"
        "- 「○○店」等が元に含まれていれば残す。\n"
        "- 「ー」（長音符）や「-」「—」「–」「─」「―」は削除しない。\n"
        "- 英数字は半角、アルファベットは大文字に統一。\n"
        "- スペースは一切入れない。括弧（“”「」()）は入れない。\n"
        "- 本来そのような名前でないのに全てカタカナ/アルファベット化する名寄せはしない。\n\n"
        "【よくある誤りを必ず修正】\n"
        "- 「イスト」→「イースト」 / 「ガデン」→「ガーデン」\n"
        "- 地名の誤読は正す（例：所沢、下富 など）\n"
        "- 余計な1文字混入（例：「ス寿司虎…」「ユゆず庵…」）は除去\n\n"
        + cand_section +
        "【不確実】\n"
        "- 推測は禁止。判断できなければ入力（クリーニング後）をそのまま返す。\n\n"
        f"【入力】\n{cleaned}\n\n"
        "【出力形式（厳守）】名称のみ1行（前後に空白なし、改行なし）\n"
        "【出力例】\n椿屋カフェ北千住マルイ店\n丸源ラーメン仙台泉店"
    )


# =========================
# OpenAI 呼び出し
# =========================
LLM_TEMPERATURE = 0.0
LLM_TOP_P = 1.0
LLM_MODEL = os.environ.get("OPENAI_MODEL_NAME", "gpt-4.1-nano")


def call_chatgpt_api(
    prompt: str,
    model: str = LLM_MODEL,
    temperature: float = LLM_TEMPERATURE,
    top_p: float = LLM_TOP_P,
    max_tokens: int = 64
) -> str:
    """
    OpenAI API ラッパ。
    ここでは例外を握りつぶさない（上位のリトライで処理するため）。
    """
    if openai is None:
        raise RuntimeError("openai package is not installed.")
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "あなたは正規化アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        n=1,
    )
    content = getattr(resp.choices[0].message, "content",
                      resp.choices[0].message["content"])
    return content.strip()


def _call_llm_with_retry(prompt: str, max_retries: int = 4) -> str:
    """503/504等の一時エラーに指数バックオフでリトライ。"""
    delay = 0.8
    for i in range(max_retries):
        try:
            return call_chatgpt_api(
                prompt,
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                top_p=LLM_TOP_P,
                max_tokens=64,
            )
        except Exception as e:
            msg = str(e)
            if any(k in msg for k in ["overloaded", "not ready", "5xx", "503", "504", "timeout"]):
                if i == max_retries - 1:
                    raise
                time.sleep(delay + random.random() * 0.25)
                delay *= 2
            else:
                raise


# =========================
# LLM 出力ガード
# =========================
def _finalize_llm_name(s: str, fallback: str) -> str:
    """
    出力は1行・スペース無し。英字は大文字化、禁止文字を除去。
    """
    if not isinstance(s, str) or not s.strip():
        return fallback
    t = s.strip().replace(' ', '').replace('\n', '')
    t = unicodedata.normalize('NFKC', t)
    t = ''.join(ch.upper() if 'a' <= ch.lower() <= 'z' else ch for ch in t)
    t = _FORBIDDEN_RE.sub('', t)
    return t or fallback


# =========================
# フィールド正規化（名寄せ）
# =========================
def normalize_field(orig: str, mapping: dict, dict_path: str, field_name: str) -> str:
    """
    名寄せ本体。既知マップ→類似候補→LLM→出力ガード→辞書追記の順で処理。
    引数 `mapping`/`dict_path` は互換性維持のために残している（未使用）。
    """
    cleaned = clean_string(orig)

    # 既知辞書ヒット
    store = load_mapping_store()
    if cleaned in store:
        return store[cleaned]

    # 類似候補（上位3件、しきい値0.80）
    store_keys = list(store.keys())
    top3 = _top_k_similar(cleaned, store_keys)
    cand_names = [store[k] for k, score in top3 if score >= CAND_THRESHOLD]

    # プロンプト作成
    prompt = _build_prompt(
        field_name=field_name,
        cleaned=cleaned,
        candidates=cand_names if cand_names else None
    )

    # LLM呼び出し（リトライ付）
    try:
        response = _call_llm_with_retry(prompt)
    except Exception as e:
        log_unmatched('名寄せ失敗', f"{field_name}: 候補={cleaned} → API失敗: {e}")
        return cleaned

    # 出力ガード
    normalized = _finalize_llm_name(response, fallback=cleaned)
    if not normalized:
        log_unmatched('名寄せ失敗', f"{field_name}: 候補={cleaned} → 正式名称取得失敗")
        return cleaned

    # 辞書に追記（同一でも追記OK）
    append_mapping(cleaned, normalized, field_name)
    store[cleaned] = normalized

    return normalized or cleaned


# ─── ヘッダ正規化 ───
def normalize_header(h: str) -> str:
    """
    Unicode NFKC → 空白類削除 → 小文字化。
    """
    if not isinstance(h, str):
        return ''
    s = unicodedata.normalize('NFKC', h)
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


def try_parse(s) -> Optional[float]:
    try:
        num = normalize_numeric_text(s)
        return float(num) if num != '' else None
    except Exception:
        return None


# ─── 金額列判定 ───
AMOUNT_KEYWORDS = [
    '売上', '売り上げ', '金額', '合計額', 'total', 'amount',
    '売上高', 'sales', 'revenue',
    '請求金額', 'ご請求金額', '請求額',
    '作業金額', '工賃',
    '手数料', 'commission', 'handling_fee',
    '運賃', '送料', 'freight', 'shipping',
]
AMOUNT_PATTERN = re.compile(r'.*費$')


def is_amount_header(hdr: str) -> bool:
    h = normalize_header(hdr)
    if h in ('売上', '売り上げ'):
        return True
    return any(kw in h for kw in AMOUNT_KEYWORDS) or bool(AMOUNT_PATTERN.match(h))


# ─── 列名正規化 ───
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    COLUMN_ALIASES に基づき、完全一致→部分一致の優先で列名を統一。
    """
    rename_map: Dict[str, str] = {}
    already_mapped: set[str] = set()

    for std_col, aliases in COLUMN_ALIASES.items():
        norm_aliases = [normalize_header(a) for a in aliases]

        # 完全一致
        for orig in df.columns:
            norm_orig = normalize_header(orig)
            if norm_orig in norm_aliases and std_col not in already_mapped:
                rename_map[orig] = std_col
                already_mapped.add(std_col)

        # 部分一致（未マッピングのみ）
        for orig in df.columns:
            norm_orig = normalize_header(orig)
            if any(alias in norm_orig for alias in norm_aliases) and std_col not in already_mapped:
                rename_map[orig] = std_col
                already_mapped.add(std_col)

    return df.rename(columns=rename_map)


# ─── 動的ヘッダ検出付き読み込み ───
def read_with_dynamic_header(path: str) -> Dict[str, pd.DataFrame]:
    """
    Excel 全シートの冒頭数行を見て、金額列が現れる行をヘッダとして読み直す。
    戻り値: { sheet_name: DataFrame(head 付き) }
    """
    all_preview: Dict[str, pd.DataFrame] = pd.read_excel(
        path, sheet_name=None, header=None, nrows=5
    )
    sheet_dfs: Dict[str, pd.DataFrame] = {}
    base = os.path.splitext(os.path.basename(path))[0]

    for sheet, preview in all_preview.items():
        key = f"{base}_{sheet}"

        # ヘッダー行検出（最初に金額らしき列を含む行）
        header_row = 0
        for i, row in preview.iterrows():
            norm = [normalize_header(str(v)) for v in row.fillna('')]
            if any(is_amount_header(h) or '金額' in h for h in norm):
                header_row = i
                break

        df = pd.read_excel(path, sheet_name=sheet, header=header_row)
        if df.empty:
            log_unmatched('読込エラー', f"{key}: 空のシートです")
            continue
        df['__source'] = key
        sheet_dfs[sheet] = df

    if not sheet_dfs:
        raise ValueError(f"{base} のシートすべてでデータが取れませんでした")
    return sheet_dfs


def parse_flexible_date(raw_date, year_hint: str) -> str:
    """
    さまざまな日付表記を YYYY/MM/DD に正規化。
    year_hint は「YYYY」。
    """
    if pd.isna(raw_date):
        return ''
    s = str(raw_date).strip()

    m = re.match(r'^(\d{1,2})月(\d{1,2})日$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    m = re.match(r'^(\d{1,2})[\/\-](\d{1,2})$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    m = re.match(r'^(\d{1,2})月(\d{1,2})$', s)
    if m:
        mm, dd = map(int, m.groups())
        return f"{year_hint}/{mm:02d}/{dd:02d}"

    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s)  # 20240109
    if m:
        y, m_, d = map(int, m.groups())
        return f"{y}/{m_:02d}/{d:02d}"

    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', s)
    if m:
        y, m_, d = map(int, m.groups())
        return f"{y}/{m_:02d}/{d:02d}"

    try:
        dt = pd.to_datetime(s, errors='coerce')
        if not pd.isna(dt):
            return dt.strftime('%Y/%m/%d')
    except Exception:
        pass

    return ''


def normalize(col: str) -> str:
    """簡易列名正規化（互換のため残置）。"""
    s = col.lower()
    s = s.translate(str.maketrans({'　': ' ', '（': '(', '）': ')'}))
    s = re.sub(r'[^\w\s]', '', s)
    s = s.replace(' ', '')
    for honorific in ['様', 'さん', '殿', '先生', '御中']:
        s = s.replace(honorific, '')
    return s


def pick_store_column(row: pd.Series, raw_cols: List[str]) -> str:
    """
    店名候補となる列から優先順位に従って値を取得。
    """
    norm_map = {normalize(c): c for c in raw_cols}
    norm_cols = list(norm_map.keys())

    patterns = [
        r'^依頼.*', r'^ご?依頼.*', r'^お客様.*', r'顧客.*', r'(クライアント)',
        r'(送|発|配)送.*先', r'宛先', r'店舗.*', r'ショップ.*',
    ]

    # パターンマッチ最優先
    for pat in patterns:
        regex = re.compile(pat)
        for nc in norm_cols:
            if regex.search(nc):
                return str(row.get(norm_map[nc], ''))

    # 部分一致フォールバック
    for nc, orig in norm_map.items():
        if any(key in nc for key in ['主', '客', '先', '店']):
            return str(row.get(orig, ''))

    # それでもなければ「店舗」列
    return str(row.get('店舗', ''))


# ─── レコード抽出 ───
def is_summary_row(row: pd.Series) -> bool:
    """
    行中の全セル文字列から空白を除去し、
    どれかに「小計/合計/総計」を含めば True。
    """
    texts = row.astype(str).str.replace(r'\s+', '', regex=True)
    return texts.str.contains(r'小計|合計|総計', na=False).any()


def extract_items(df: pd.DataFrame, meta: dict) -> List[dict]:
    """
    明細レコード抽出。小計/合計行除外、日付/数量/単価/金額/店名を整形。
    """
    # 小計・合計行を除外
    df = df.loc[~df.apply(is_summary_row, axis=1)]

    raw_cols = list(df.columns)
    norm_cols = [normalize_header(c) for c in raw_cols]

    # 日付列補正（見つかった場合のみ）
    date_col = next((c for c in raw_cols if normalize_header(c) == '日付'), None)
    if date_col:
        ym = meta['年月']  # "YYYY-MM"
        default_date = f"{ym}-01"
        df[date_col] = df[date_col].fillna('')
        df[date_col] = df[date_col].apply(
            lambda x: parse_flexible_date(x, ym.split('-')[0]) or default_date
        )

    idx_qty = next((i for i, h in enumerate(norm_cols) if h.endswith('数量')), None)
    idx_unit = next((i for i, h in enumerate(norm_cols) if '単価' in h), None)

    # 金額列候補を抽出
    amt_cands = [c for c in raw_cols if is_amount_header(c)]
    total_cands = [
        c for c in amt_cands
        if '合計' in normalize_header(c) or 'total' in normalize_header(c)
    ]

    # 合計列を優先
    if total_cands:
        sums = {c: df[c].map(lambda x: try_parse(x) or 0).sum() for c in total_cands}
        chosen = max(sums, key=sums.get)
        idx_amount = raw_cols.index(chosen)
    elif amt_cands:
        idx_amount = raw_cols.index(amt_cands[0])
    else:
        log_unmatched('列検出エラー', f"{meta['filepath']}: 金額列が見つかりません")
        return []

    recs: List[dict] = []
    for row_i, row in df.iterrows():
        raw_date = row.get('日付')
        year_hint = meta.get('年月', '').split('-')[0]
        date_str = parse_flexible_date(raw_date, year_hint)
        if not date_str:
            log_unmatched('日付抽出失敗', f"{meta['filepath']}#行{row_i}: 元値={raw_date}")
            continue

        # 数量
        if idx_qty is None or df.iloc[:, idx_qty].isna().all():
            q = 1
        else:
            q = try_parse(row.iloc[idx_qty])

        # 単価
        p = try_parse(row.iloc[idx_unit]) if idx_unit is not None else None
        if p is not None:
            p = round(p, 1)

        # 金額
        a = try_parse(row.iloc[idx_amount])
        if a is None:
            log_unmatched(
                '金額欠損',
                f"{meta['filepath']}#行{row_i}: 列={raw_cols[idx_amount]}, 値={row.iloc[idx_amount]}"
            )
            continue

        raw_store = pick_store_column(row, raw_cols)
        store = normalize_field(raw_store, {}, MAPPING_STORE_PATH, '店舗名')
        item = clean_string(row.get('作業項目/商品名', ''))

        recs.append({
            '部署': meta.get('部署', ''),
            '下請け': meta.get('下請け', ''),
            '日付': date_str,
            '店舗名': store,
            '作業項目/商品名': item,
            '数量': q,
            '単価': p,
            '金額': a,
        })

    return recs


def filter_duplicates_by_basename(file_paths: List[str]) -> set[str]:
    """
    同一 basename をもつファイルが複数ある場合、
    更新日時最新の１件だけ残す。
    """
    groups: Dict[str, List[str]] = {}
    for p in file_paths:
        bn = os.path.basename(p)
        groups.setdefault(bn, []).append(p)

    kept: set[str] = set()
    for bn, paths in groups.items():
        if len(paths) == 1:
            kept.add(paths[0])
        else:
            latest = max(paths, key=lambda x: os.path.getmtime(x))
            kept.add(latest)
            for other in paths:
                if other != latest:
                    log_unmatched('重複ファイル', f"{other} は {latest} と同名のためスキップ")
    return kept


# ─── メイン処理 ───
def handle_new_file(filepath: str) -> None:
    """
    監視フォルダに着弾したファイルをトリガに、同月/同年ファイルを再集計し出力する。
    """
    from watch_folder import archive_file
    watch_dir_abs = Path(WATCH_DIR).resolve()

    def _in_watch_dir(p: str) -> bool:
        try:
            pr = Path(p).resolve()
            return pr == watch_dir_abs or watch_dir_abs in pr.parents
        except Exception:
            return False

    # ① ファイル名パース
    meta = parse_filename(filepath)
    if 'エラー' in meta:
        log_unmatched('ファイル名', filepath)
        return

    ym = meta['年月']        # "YYYY-MM"
    year = ym.split('-')[0]  # "YYYY"
    notice("集計を開始しました", 年月=ym)

    # ③ 候補ファイル収集（WATCH_DIR + PROCESSED_DIR）
    candidates_month: List[Tuple[str, dict]] = []
    candidates_year: List[Tuple[str, dict]] = []
    for base in (WATCH_DIR, PROCESSED_DIR):
        for root, _, files in os.walk(base):
            for fn in files:
                if fn.startswith('~$'):
                    continue
                fullpath = os.path.join(root, fn)
                m = parse_filename(fullpath)
                if 'エラー' in m:
                    continue
                if m.get('年月') == ym:
                    candidates_month.append((fullpath, m))
                if m.get('年月', '').split('-', 1)[0] == year:
                    candidates_year.append((fullpath, m))

    # ④ 月次：basename 重複排除 → 抽出 → （WATCH内のみ）アーカイブ
    month_paths = [p for p, _ in candidates_month]
    kept_month = set(filter_duplicates_by_basename(month_paths))
    all_records_month: List[dict] = []

    for path, m in candidates_month:
        if path not in kept_month:
            continue
        m['filepath'] = path

        try:
            if path.lower().endswith('.csv'):
                base = os.path.splitext(os.path.basename(path))[0]
                sheets = {base: pd.read_csv(path)}
            else:
                sheets = read_with_dynamic_header(path)
        except Exception:
            exception("月次ファイルの読み込みに失敗しました", ファイル=path)
            raise

        for sheet_name, df in sheets.items():
            try:
                df2 = normalize_columns(df)
            except Exception:
                exception("列名の正規化に失敗しました", ファイル=path, シート=sheet_name)
                raise

            try:
                m_sheet = m.copy()
                m_sheet['sheet'] = sheet_name
                recs = extract_items(df2, m_sheet)
            except Exception:
                exception("明細の抽出に失敗しました", ファイル=path, シート=sheet_name)
                raise

            all_records_month.extend(recs)

        # ウォッチ内のものだけアーカイブ
        if _in_watch_dir(path):
            archive_file(path, success=True)

    df_month = pd.DataFrame(all_records_month)
    notice("月次の抽出が完了しました", レコード件数=len(df_month))

    # ⑤ 年次：パス補正 → basename 重複排除 → 抽出 → （WATCH内のみ）アーカイブ
    corrected: List[Tuple[str, dict]] = []
    for path, m in candidates_year:
        if not os.path.exists(path):
            alt = os.path.join(PROCESSED_DIR, m['部署'], os.path.basename(path))
            if os.path.exists(alt):
                path = alt
        corrected.append((path, m))

    year_paths = [p for p, _ in corrected]
    kept_year = set(filter_duplicates_by_basename(year_paths))
    all_records_year: List[dict] = []

    for path, m in corrected:
        if path not in kept_year:
            continue
        m['filepath'] = path
        in_watch = _in_watch_dir(path)

        try:
            if path.lower().endswith('.csv'):
                base = os.path.splitext(os.path.basename(path))[0]
                sheets = {base: pd.read_csv(path)}
            else:
                sheets = read_with_dynamic_header(path)

            for sheet_name, df in sheets.items():
                # 年次側は元の流れを踏襲し、列名を一旦正規化してから alias 適用
                df.columns = [normalize_header(c) for c in df.columns]
                df2 = normalize_columns(df)

                m_sheet = m.copy()
                m_sheet['sheet'] = sheet_name
                recs = extract_items(df2, m_sheet)
                all_records_year.extend(recs)

            # 正常終了時のみ、WATCHに居るファイルをアーカイブ
            if in_watch:
                archive_file(path, success=True)

        except Exception as e:
            log_unmatched('読込エラー', f"{path}: {e}")  # CSV にも残す
            # 失敗時のアーカイブも WATCH にある場合のみ・1回だけ
            if in_watch:
                archive_file(path, success=False)

    df_year = pd.DataFrame(all_records_year)
    notice("年次の抽出が完了しました", レコード件数=len(df_year))

    # ⑥ 出力設定（列幅マップ）
    col_widths = {
        '部署': 8, '下請け': 20, '日付': 20,
        '店舗名': 45, '作業項目/商品名': 60,
        '数量': 8, '単価': 15, '金額': 20,
    }

    # ⑥-1) 月次部署別出力
    base_month = f"{ym}_records"
    for dept, grp in df_month.groupby('部署'):
        out_dir = os.path.join(OUTPUT_DIR, dept)
        os.makedirs(out_dir, exist_ok=True)

        subs = grp.groupby('下請け', as_index=False)[['数量', '金額']].sum()
        subs['作業項目/商品名'] = '小計'
        total = {
            '部署': dept, '下請け': '', '日付': '',
            '店舗名': '', '作業項目/商品名': '合計',
            '数量': grp['数量'].sum(), '単価': '', '金額': grp['金額'].sum(),
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
            fmt = wb.add_format({'num_format': '#,##0'})
            for i, col in enumerate(grp_ext.columns):
                ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
            ws.autofilter(0, 0, len(grp_ext), len(grp_ext.columns) - 1)

    # ⑥-2) 月次全社統合出力
    all_mon = os.path.join(OUTPUT_DIR, '_全社統合')
    os.makedirs(all_mon, exist_ok=True)
    subs_c = df_month.groupby('下請け', as_index=False)[['数量', '金額']].sum().assign(
        部署='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名': '会社小計'}
    )
    subs_d = df_month.groupby('部署', as_index=False)[['数量', '金額']].sum().assign(
        下請け='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名': '部署小計'}
    )
    total_all = {
        '部署': '', '下請け': '', '日付': '',
        '店舗名': '', '作業項目/商品名': '全社合計',
        '数量': df_month['数量'].sum(), '単価': '', '金額': df_month['金額'].sum(),
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
        fmt = wb.add_format({'num_format': '#,##0'})
        for i, col in enumerate(df_ext.columns):
            ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
        ws.autofilter(0, 0, len(df_ext), len(df_ext.columns) - 1)

    # ⑥-3) 年次部署別出力
    for dept, grp in df_year.groupby('部署'):
        year_dir = os.path.join(OUTPUT_DIR, dept, 'yearly')
        os.makedirs(year_dir, exist_ok=True)
        base_year = f"{dept}_{year}_records"

        subs = grp.groupby('下請け', as_index=False)[['数量', '金額']].sum()
        subs['作業項目/商品名'] = '部署小計'
        total = {
            '部署': dept, '下請け': '', '日付': '',
            '店舗名': '', '作業項目/商品名': '年次合計',
            '数量': grp['数量'].sum(), '単価': '', '金額': grp['金額'].sum(),
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
            fmt = wb.add_format({'num_format': '#,##0'})
            for i, col in enumerate(grp_ext.columns):
                ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
            ws.autofilter(0, 0, len(grp_ext), len(grp_ext.columns) - 1)

    # ⑥-4) 年次全社統合出力
    company_year_dir = os.path.join(OUTPUT_DIR, '_全社統合', 'yearly')
    os.makedirs(company_year_dir, exist_ok=True)
    subs_cy = df_year.groupby('下請け', as_index=False)[['数量', '金額']].sum().assign(
        部署='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名': '会社小計'}
    )
    subs_dy = df_year.groupby('部署', as_index=False)[['数量', '金額']].sum().assign(
        下請け='', 日付='', 単価='', 店舗名='', **{'作業項目/商品名': '部署小計'}
    )
    total_yr = {
        '部署': '', '下請け': '', '日付': '',
        '店舗名': '', '作業項目/商品名': '年次合計',
        '数量': df_year['数量'].sum(), '単価': '', '金額': df_year['金額'].sum(),
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
        fmt = wb.add_format({'num_format': '#,##0'})
        for i, col in enumerate(df_yr_ext.columns):
            ws.set_column(i, i, col_widths.get(col, 15), fmt if col == '金額' else None)
        ws.autofilter(0, 0, len(df_yr_ext), len(df_yr_ext.columns) - 1)

    notice("集計が完了しました", 年月=ym)

    # ── 処理完了通知──
    try:
        from notifier import notify
        notify("Keiri 処理完了", os.path.basename(filepath) + " の処理が終わりました。", duration=5)
    except Exception:
        pass
