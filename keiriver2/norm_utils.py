# keiriver2/norm_utils.py
import difflib
import unicodedata
import re
import time, random

# ---- 類似度まわり ----
CAND_THRESHOLD = 0.80  # 0.80以上のみ候補に採用
TOP_K = 3

def _trigrams(s: str):
    return [s[i:i+3] for i in range(max(1, len(s)-2))]

def _jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(1, len(sa | sb))

def _brand_token(s: str):
    for sep in ("店", " ", "　"):
        idx = s.find(sep)
        if idx > 0:
            return s[:idx]
    return s[:min(6, len(s))]

def similarity(a: str, b: str) -> float:
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    j = _jaccard(_trigrams(a), _trigrams(b))
    bonus = 0.1 if _brand_token(a) == _brand_token(b) else 0.0
    return 0.6 * seq + 0.4 * j + bonus

def top_k_similar(cleaned: str, store_keys):
    scored = [(key, similarity(cleaned, key)) for key in store_keys]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:TOP_K]

# ---- LLM & 出力ガード ----
FORBIDDEN_CHARS = '「」『』“”‘’()[]{}<>・：；。，、!?？…'
_forbidden_re = re.compile(f"[{re.escape(FORBIDDEN_CHARS)}]")

def finalize_llm_name(s: str, fallback: str) -> str:
    if not isinstance(s, str) or not s.strip():
        return fallback
    s = s.strip().replace(' ', '').replace('\n', '')
    s = unicodedata.normalize('NFKC', s)
    s = ''.join(ch.upper() if 'a' <= ch.lower() <= 'z' else ch for ch in s)
    s = _forbidden_re.sub('', s)
    return s or fallback

def call_llm_with_retry(call_fn, prompt: str, max_retries=4):
    delay = 0.8
    for i in range(max_retries):
        try:
            # call_fn は (prompt) -> str を想定（あなたの実装を渡す）
            return call_fn(prompt)
        except Exception as e:
            msg = str(e)
            if any(k in msg for k in ["overloaded", "not ready", "5xx", "503", "504", "server"]):
                if i == max_retries - 1:
                    raise
                time.sleep(delay + random.random() * 0.25)
                delay *= 2
            else:
                raise

def build_prompt(field_name: str, cleaned: str, candidates: list[str] | None) -> str:
    cand_line = (" / ".join(candidates)) if candidates else ""
    cand_section = f"【候補】{cand_line}\n" if candidates else ""
    return (
        f"{field_name} の店舗名を1つに正規化してください。\n"
        "【規則】法人格/部門/様/分/スタッフは除外。「○○店」は残す。長音符/ハイフン類は削除しない。"
        "英数字は半角、英字は大文字。スペースと括弧は使わない。\n"
        + cand_section +
        "【不確実】推測禁止。判断できなければ入力（クリーニング後）をそのまま返す。\n"
        f"【入力】{cleaned}\n"
        "【出力】名称のみ1行"
    )
