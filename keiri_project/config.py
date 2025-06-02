import os

# ==== Paths ====
BASE_DIR = os.path.dirname(__file__)
WATCH_DIR = r"C:\Users\8963948\Desktop\帳簿アップロード"
TEMP_ROOT = os.path.join(WATCH_DIR, "temp")
OUTPUT_ROOT = os.path.join(WATCH_DIR, "output")
MANUAL_DICT_PATH = os.path.join(BASE_DIR, "mapping_manual.csv")
AUTO_DICT_PATH = os.path.join(BASE_DIR, "mapping_auto.csv")
API_KEY_PATH = os.path.join(BASE_DIR, "api_key.txt")

# ==== Column mappings ====
COLUMN_MAP = {
    "企業名": ["企業", "得意先", "発送先", "お客様", "支払先", "お客様名", "店舗", "店舗名"],
    "金額": [
        "金額", "売上", "売上金額", "売上合計", "販売金額", "売上収益",
        "請求金額", "請求額", "請求合計", "請求予定", "支払金額", "支払額",
        "支払合計", "支出", "原価", "原価合計", "仕入金額", "コスト",
        "実績金額", "合計金額", "伝票合計", "総額", "作業金額",
        "ご請求金額", "弊社→御社"
    ],
    "分類": ["分類", "区分", "カテゴリ", "品目"],
    "店舗名": ["店舗名", "お客様名", "送り先", "発送先名", "ご依頼主"],
    "商品名": ["作業内容", "内容", "商品名", "商品"],
    "数量": ["数量", "個数", "本数", "数"],
    "単価": ["単価", "価格", "単価（税込）"]
}