# logger.py

import os
import csv
import logging
import sys
from config import UNMATCHED_LOG, WATCH_LOG

# ── CSV ログのヘッダー準備 ──
os.makedirs(os.path.dirname(UNMATCHED_LOG), exist_ok=True)
if not os.path.exists(UNMATCHED_LOG):
    with open(UNMATCHED_LOG, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['カテゴリ', '値', 'エラー内容'])

# ── テキスト稼働ログの設定 ──
os.makedirs(os.path.dirname(WATCH_LOG), exist_ok=True)
logger = logging.getLogger("keiri")
logger.setLevel(logging.INFO)

# ファイル出力ハンドラ
fh = logging.FileHandler(WATCH_LOG, encoding='utf-8')
fh.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))
logger.addHandler(fh)

# コンソールハンドラ（開発時のデバッグ用）
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(ch)

def log_unmatched(category: str, value: str, note: str = ""):
    """
    エラー／未整形情報は CSV へ、
    稼働ログはテキストファイルへ同時に出力します。
    """
    # 1) CSV 追記
    with open(UNMATCHED_LOG, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([category, value, note])

    # 2) テキストログ warning レベルで残す
    logger.warning(f"{category} | {value} | {note}")

# 例：ウォッチャー開始・停止などの稼働イベントも記録可能
def log_info(message: str):
    logger.info(message)
