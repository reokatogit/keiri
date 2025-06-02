import os
import pandas as pd
from datetime import datetime
import ctypes
from keiri_project.logger import log_unmatched
from keiri_project.config import MANUAL_DICT_PATH, AUTO_DICT_PATH, API_KEY_PATH
from keiri_project.api_key_loader import get_openai_api_key

# ======= ChatGPT補完設定 =======
USE_CHATGPT = True
OPENAI_API_KEY = get_openai_api_key()

def load_api_key_with_prompt():
    global OPENAI_API_KEY
    if not os.path.exists(API_KEY_PATH) or os.path.getsize(API_KEY_PATH) == 0:
        choice = ctypes.windll.user32.MessageBoxW(
            0,
            "ChatGPT補完が有効ですが、APIキーが設定されていません。\n\n"
            "未設定のまま始めますか？（分類や名寄せ補完は行われません）",
            "🔑 APIキー未設定",
            0x33  # YESNO + ICONQUESTION
        )
        if choice == 6:  # IDYES
            OPENAI_API_KEY = ""
        else:
            os.startfile(API_KEY_PATH if os.path.exists(API_KEY_PATH) else ".")
            raise SystemExit("APIキーを設定してください。")
    else:
        with open(API_KEY_PATH, "r", encoding="utf-8") as f:
            OPENAI_API_KEY = f.read().strip()

if USE_CHATGPT:
    load_api_key_with_prompt()

# ======= 辞書読み込み =======
mapping_dict = {}
store_dict = {}

for path in (MANUAL_DICT_PATH, AUTO_DICT_PATH):
    if os.path.exists(path):
        df = pd.read_csv(path, encoding='utf-8')
        if {'raw', 'standard'}.issubset(df.columns):
            mapping_dict.update(dict(zip(df['raw'], df['standard'])))

STORE_DICT_PATH = os.path.join(os.path.dirname(__file__), 'mapping_store.csv')
if os.path.exists(STORE_DICT_PATH):
    df_store = pd.read_csv(STORE_DICT_PATH, encoding='utf-8')
    if {'raw', 'standard'}.issubset(df_store.columns):
        store_dict.update(dict(zip(df_store['raw'], df_store['standard'])))

# ======= ChatGPT呼び出し =======
def ask_chatgpt(prompt: str) -> str:
    if not USE_CHATGPT or not OPENAI_API_KEY:
        return None
    import openai
    try:
        openai.api_key = OPENAI_API_KEY
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは表記揺れを正規化するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return None

# ======= 補完バリデーション =======
def is_valid_completion(raw: str, std: str) -> bool:
    if not std:
        return False
    if std.lower() in ("不明", "なし", "none"):
        return False
    if std.strip().lower() == raw.strip().lower():
        return False
    return True

# ======= 名寄せ：企業名 =======
def normalize_name(name: str, source_file: str, column: str, output_dir: str) -> str:
    if name in mapping_dict:
        return mapping_dict[name]
    prompt = (
        "この企業名は会計帳簿に記載されたものです。\n"
        "正式名称として一般的に使われている表記に変換してください:\n"
        + name
    )
    std = ask_chatgpt(prompt)
    if is_valid_completion(name, std):
        mapping_dict[name] = std
        df = pd.DataFrame([{
            "raw": name,
            "standard": std,
            "source": os.path.basename(source_file),
            "method": "chatgpt",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        df.to_csv(AUTO_DICT_PATH, mode='a', header=not os.path.exists(AUTO_DICT_PATH), index=False, encoding='utf-8')
        return std
    log_unmatched(name, source_file, column, output_dir)
    return name

# ======= 名寄せ：店舗名 =======
def normalize_store_name(name: str, source_file: str, column: str, output_dir: str) -> str:
    if name in store_dict:
        return store_dict[name]
    prompt = (
        "次の店舗名は会計帳簿に記載されたものです。\n"
        "正式な店名として一般的に使われる表記に変換してください:\n"
        + name
    )
    std = ask_chatgpt(prompt)
    if is_valid_completion(name, std):
        store_dict[name] = std
        df = pd.DataFrame([{
            "raw": name,
            "standard": std,
            "source": os.path.basename(source_file),
            "method": "chatgpt",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        os.makedirs(os.path.dirname(STORE_DICT_PATH), exist_ok=True)
        df.to_csv(STORE_DICT_PATH, mode='a', header=not os.path.exists(STORE_DICT_PATH), index=False, encoding='utf-8')
        return std
    log_unmatched(name, source_file, column, output_dir, reason="店舗名補完失敗")
    return name
