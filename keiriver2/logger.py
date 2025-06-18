# logger.py
import os
import csv
from config import UNMATCHED_LOG

# ファイルがなければヘッダーを書いておく
if not os.path.exists(UNMATCHED_LOG):
    with open(UNMATCHED_LOG, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['カテゴリ', '値', 'エラー内容'])

def log_unmatched(category: str, value: str, note: str = ""):
    """
    未整形・エラー情報を CSV に書くだけ。
    GUI は一切出さない。
    """
    with open(UNMATCHED_LOG, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([category, value, note])
