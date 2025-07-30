#config.py 
import os
from pathlib import Path

# ── 1) 生ファイル投入フォルダ
WATCH_DIR = str(Path.home() / "Desktop" / "帳簿アップロード")
os.makedirs(WATCH_DIR, exist_ok=True)

# ── 2) 出力結果フォルダ
OUTPUT_DIR = os.path.join(WATCH_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 3) アーカイブ用フォルダ（成功時）
PROCESSED_DIR = os.path.join(WATCH_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ── 3b) アーカイブ用フォルダ内のエラー時出力先
ERROR_DIR = os.path.join(PROCESSED_DIR, "errors")
os.makedirs(ERROR_DIR, exist_ok=True)

# ── 4) 一時ファイル用
TEMP_ROOT = os.path.join(os.path.dirname(__file__), 'temp')
os.makedirs(TEMP_ROOT, exist_ok=True)

# ── 5) 未マッチログ
UNMATCHED_LOG = os.path.join(os.path.dirname(__file__), 'unmatched_final.csv')

# ── 6) 名寄せ辞書ファイルパス
COMPANY_DICT_PATH  = os.path.join(os.path.dirname(__file__), 'company_dict.csv')
STORE_DICT_PATH    = os.path.join(os.path.dirname(__file__), 'store_dict.csv')
MAPPING_STORE_PATH = os.path.join(os.path.dirname(__file__), 'mapping_store.csv')

# ── 7) 列名エイリアス定義
COLUMN_ALIASES = {
    '企業':     ['企業名', '取引先', '会社名'],
    '店舗':     ['店舗名', '納品先', '送り先', 'お届け先'],
    '日付':     ['日付', '納品日', '売上日', '作業日', '配達完了', '訪問日', '出荷日'],
    '作業項目/商品名': ['作業内容', 'サービス項目', '作業項目', '商品', '品名', '内容', '商品名'],
    '数量':     ['数量', '数', '個数'],
    '単価':     ['単価', '値段'],
    '金額':     ['金額', '売売上', '支払額', '小計'],
    '分類':     ['分類', '区分'],
}

# ── 8) OpenAI API キー設定（keyring or テキスト保存）
API_KEY_PATH   = os.path.join(os.path.dirname(__file__), 'openai_api_key.txt')
OPENAI_API_KEY = None

# ── 9) 監視設定
#    デフォルト間隔。settings.py から読み書きするベース値として使います
DEFAULT_INTERVAL = 10

# 起動時に settings.json があれば上書きされます
CHECK_INTERVAL   = DEFAULT_INTERVAL
VALID_EXTENSIONS = ('.xlsx', '.xls', '.csv')

# ── 10) 設定ファイルパス（ユーザーごとに隠しファイルとして保存）
CONFIG_PATH = os.path.expanduser("~/.keiri_config.json")


# 未整形・エラー情報の CSV ログ
UNMATCHED_LOG = os.path.join('log', 'unmatched.csv')

# ウォッチャー稼働ログ（タスクトレイの「ログを見る」で開く）
WATCH_LOG = os.path.join('log', 'watch_folder.log')

# 確実に log フォルダが存在するようにアプリ起動時に呼んでください
os.makedirs(os.path.dirname(UNMATCHED_LOG), exist_ok=True)
