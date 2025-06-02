# -*- coding: utf-8 -*-
import os
import re
import pandas as pd
from datetime import datetime
from keiri_project.config import BASE_DIR
from keiri_project.normalizer import ask_chatgpt, is_valid_completion
from keiri_project.api_key_loader import get_openai_api_key

USE_CHATGPT = True
OPENAI_API_KEY = get_openai_api_key()

# ————————————————————————————
# 分類ルール実装ライブラリ
# ————————————————————————————

# パス設定：分類辞書ファイル（手動／自動）
CLASS_MANUAL_PATH = os.path.join(BASE_DIR, 'classification_manual.csv')
CLASS_AUTO_PATH = os.path.join(BASE_DIR, 'classification_auto.csv')

# 辞書読み込み
class_manual = {}
class_auto = {}
for path, storage in ((CLASS_MANUAL_PATH, class_manual), (CLASS_AUTO_PATH, class_auto)):
    if os.path.exists(path):
        df = pd.read_csv(path, encoding='utf-8')
        if {'raw','standard'}.issubset(df.columns):
            storage.update(dict(zip(df['raw'], df['standard'])))

# キーワードベース分類
item_keywords = ["ロール紙", "プリンター", "ケーブル", "OAタップ", "端末"]
task_keywords = ["設置", "設定", "保守", "対応", "サポート", "レクチャー", "納品書", "運賃"]

# 1. 部署名・企業名抽出(いらない？)
def extract_department_company(filename: str):
    parts = filename.replace(".xlsx", "").split("_")
    department = parts[0] if parts else ""
    company = next((p for p in parts if "株式会社" in p or "有限会社" in p), "")
    return department, company

# 2. 日付処理（○月○日 → YYYY/MM/DD）
def parse_date(date_str: str, fallback_year: int = None):
    try:
        if "月" in date_str and "日" in date_str and fallback_year:
            md = date_str.replace("月", "/").replace("日", "")
            return pd.to_datetime(f"{fallback_year}/{md}").strftime("%Y/%m/%d")
        return pd.to_datetime(date_str).strftime("%Y/%m/%d")
    except:
        return ""

# 3. 送り先正規化（敬称・「様分」除去）
def normalize_receiver(receiver_str: str):
    return re.sub(r"(様|殿)?分?$", "", str(receiver_str)).strip()

# 4. 識別子整形（float→int→str）
def normalize_identifier(value):
    try:
        return str(int(float(value)))
    except:
        return str(value)

# 5. 要確認ログ用
_uncertain_logs = []
def log_uncertain_case(row, reason="要GPT分類"):
    entry = row.to_dict()
    entry["要確認理由"] = reason
    _uncertain_logs.append(entry)
def get_uncertain_log_df():
    return pd.DataFrame(_uncertain_logs)

# 6. GPTによる分類補完
USE_CHATGPT = True  # 実行時に True/OPENAI_API_KEY 設定で有効化

def gpt_classify(text: str) -> str:
    prompt = (
        "以下のテキストは帳簿明細の項目です。\n"
        "これが『商品名』か『作業項目』か『不明』かを、必ず1語で答えてください。\n"
        f"テキスト：{text}\n"
        "回答形式：商品 または 作業 または 不明"
    )
    res = ask_chatgpt(prompt)
    if res:
        for token in ['商品','作業','不明']:
            if token in res:
                return token
    return ""

# 7. 商品／作業分類判定（辞書→キーワード→GPT→要確認）
def classify_entry(name: str):
    text = str(name).strip()
    if not text:
        return "", ""
    # 辞書優先
    if text in class_manual:
        cat = class_manual[text]
    elif text in class_auto:
        cat = class_auto[text]
    # キーワード
    elif any(kw in text for kw in task_keywords):
        cat = '作業'
    elif any(kw in text for kw in item_keywords):
        cat = '商品'
    # GPT補完
    else:
        if USE_CHATGPT:
            cat = gpt_classify(text)
            if cat in ('商品','作業'):
                # 自動辞書に保存
                class_auto[text] = cat
                df = pd.DataFrame([{'raw':text,'standard':cat,'timestamp':datetime.now().isoformat()}])
                df.to_csv(CLASS_AUTO_PATH, mode='a', header=not os.path.exists(CLASS_AUTO_PATH), index=False, encoding='utf-8')
            else:
                cat = ''
        else:
            cat = ''
    # 要確認または分類結果
    if cat == '商品':
        return text, ''
    elif cat == '作業':
        return '', text
    else:
        return '', '要GPT分類'