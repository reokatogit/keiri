# logger.py

import os
import csv
import logging
import sys
from logging.handlers import RotatingFileHandler

# -------- 設定の取り込み（足りなければデフォルト） --------
try:
    from config import UNMATCHED_LOG, WATCH_LOG, LOG_MAX_BYTES, LOG_BACKUP_COUNT, ENABLE_CONSOLE_LOG
except Exception:
    UNMATCHED_LOG = os.path.join("logs", "unmatched.csv")
    WATCH_LOG = os.path.join("logs", "watch.log")
    LOG_MAX_BYTES = 1_000_000       # 約1MBでローテーション
    LOG_BACKUP_COUNT = 5            # 世代数
    ENABLE_CONSOLE_LOG = False      # 本番は False 推奨

# -------- CSV ログ（未整形・エラー系）の初期化 --------
os.makedirs(os.path.dirname(UNMATCHED_LOG), exist_ok=True)
if not os.path.exists(UNMATCHED_LOG):
    with open(UNMATCHED_LOG, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow(['カテゴリ', '値', 'エラー内容'])

# -------- テキスト稼働ログ（ユーザーが見る想定） --------
os.makedirs(os.path.dirname(WATCH_LOG), exist_ok=True)
logger = logging.getLogger("keiri")
logger.setLevel(logging.INFO)
logger.propagate = False  # 二重出力防止

class JpLevelFormatter(logging.Formatter):
    JP = {
        logging.INFO: "お知らせ",
        logging.WARNING: "注意",
        logging.ERROR: "エラー",
        logging.CRITICAL: "エラー",
    }
    def format(self, record):
        orig = record.levelname
        record.levelname = self.JP.get(record.levelno, orig)
        try:
            return super().format(record)
        finally:
            record.levelname = orig

_fmt = JpLevelFormatter('[%(asctime)s][%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')

# ファイル（ローテーション）
if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
    fh = RotatingFileHandler(WATCH_LOG, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding='utf-8')
    fh.setFormatter(_fmt)
    logger.addHandler(fh)

# コンソール（開発時のみ）
if ENABLE_CONSOLE_LOG and not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(_fmt)
    logger.addHandler(ch)

# -------- ユーザー向けメッセージ整形 --------
def _fmt_num(v):
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            # 小数は桁区切り（末尾.0はそのまま）／文字列はそのまま
            return f"{v:,}"
    except Exception:
        pass
    return str(v)

def _compose(title: str, **fields) -> str:
    details = " / ".join(f"{k}: { _fmt_num(v) }" for k, v in fields.items() if v not in (None, ""))
    return f"{title} — {details}" if details else title

# -------- 公開API（運用で使う3関数） --------
def notice(title: str, **fields):
    """通常進捗・結果（対応不要）"""
    logger.info(_compose(title, **fields))

def caution(title: str, **fields):
    """軽度の問題（確認推奨／データを捨てた等）"""
    logger.warning(_compose(title, **fields))

def error(title: str, **fields):
    """処理継続できない・一部失敗（対応必須）"""
    logger.error(_compose(title, **fields))

def exception(title: str, **fields):
    """例外付きのエラーログ（スタックも保存）"""
    logger.error(_compose(title, **fields), exc_info=True)

# -------- 後方互換API（既存呼び出しを壊さない） --------
def log_unmatched(category: str, value: str, note: str = ""):
    """
    未整形・エラー情報は CSV へ、概要はテキストへ（[注意]）出力。
    """
    with open(UNMATCHED_LOG, 'a', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow([category, value, note])
    logger.warning(_compose(category, 値=value, メモ=note))

def log_info(message: str):
    """旧API：INFOで素通し"""
    logger.info(message)
