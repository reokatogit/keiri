# utils.py
import unicodedata
import re
import pandas as pd
from rapidfuzz import process, fuzz
from logger import log_unmatched

def clean_string(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("‐","-").replace("–","-").replace("—","-").replace("―","-")
    return re.sub(r'\s+', ' ', s).strip()

def call_chatgpt(prompt: str, category: str) -> str | None:
    import openai
    if not getattr(openai, "api_key", None):
        return None
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role":"user","content":prompt}],
            max_tokens=50
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log_unmatched(f"{category}APIエラー", str(e))
        return None

def normalize_field(orig: str, mapping: dict, dict_path: str, field_name: str) -> str:
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
    # APIフォールバック
    std = call_chatgpt(f"この{field_name}を業務上の標準表記にしてください：{s}", field_name)
    if std:
        try:
            with open(dict_path, 'a', encoding='utf-8', newline='') as f:
                f.write(f"{s},{std}\n")
            mapping[s] = std
            return std
        except:
            pass
    log_unmatched(f"{field_name}未正規化", orig)
    return ""
