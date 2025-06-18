# watch_folder.py

import os
import time
import shutil
import threading
from processor import handle_new_file
from parser import parse_filename
from config import (
    WATCH_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    ERROR_DIR,
    CHECK_INTERVAL,
    VALID_EXTENSIONS,
    CONFIG_PATH
)
import json

# ファイルパス → 最終処理時刻（mtime）を記録
processed_time: dict[str, float] = {}

# 停止フラグ
_stop_event = threading.Event()

def _load_settings():
    """CONFIG_PATH があれば読み込み、CHECK_INTERVAL を更新"""
    global CHECK_INTERVAL
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        CHECK_INTERVAL = cfg.get("check_interval", CHECK_INTERVAL)

# 初回設定読み込み
_load_settings()

def is_valid_file(name: str) -> bool:
    return (
        name.lower().endswith(VALID_EXTENSIONS)
        and not name.startswith('~$')
    )

def wait_until_stable(path: str, interval: float = 1.0, retries: int = 3) -> bool:
    try:
        prev = os.path.getsize(path)
        for _ in range(retries):
            time.sleep(interval)
            curr = os.path.getsize(path)
            if curr == prev:
                return True
            prev = curr
    except OSError:
        return False
    return False

def archive_file(path: str, success: bool) -> None:
    meta = parse_filename(path)
    dept = meta.get('部署', 'unknown')
    dest_dir = PROCESSED_DIR if success else ERROR_DIR
    dest = os.path.join(dest_dir, dept) if success else dest_dir
    os.makedirs(dest, exist_ok=True)
    try:
        shutil.move(path, os.path.join(dest, os.path.basename(path)))
        print(f"[ARCHIVE] {path} → {dest}")
    except Exception as e:
        print(f"[WARN] アーカイブ失敗: {e}")

def run_batch_watcher() -> None:
    """
    永続ループ：WATCH_DIR を再帰スキャンし、
    新規／更新ファイルを処理＆アーカイブ。
    """
    print(f"[監視開始] {WATCH_DIR} を {CHECK_INTERVAL}秒ごとに再帰チェック")
    while not _stop_event.is_set():
        for root, _, files in os.walk(WATCH_DIR):
            # アーカイブや出力フォルダはスキップ
            if root.startswith(PROCESSED_DIR) or root.startswith(OUTPUT_DIR):
                continue

            for fname in files:
                if not is_valid_file(fname):
                    continue
                path = os.path.join(root, fname)

                if not wait_until_stable(path):
                    print(f"[スキップ] 書き込み中: {path}")
                    continue

                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue

                prev = processed_time.get(path, 0.0)
                if mtime > prev:
                    print(f"[処理] {path}")
                    try:
                        handle_new_file(path)
                        archive_file(path, success=True)
                    except Exception as e:
                        print(f"[エラー] {path}: {e}")
                        archive_file(path, success=False)
                    finally:
                        processed_time[path] = mtime
        time.sleep(CHECK_INTERVAL)

def run_batch_watcher_loop():
    """タスクトレイから呼び出す用：停止フラグをクリアして永続ループを起動"""
    _stop_event.clear()
    run_batch_watcher()

def stop_batch_watcher():
    """run_batch_watcher のループを抜けさせるフラグを立てる"""
    _stop_event.set()

if __name__ == "__main__":
    run_batch_watcher()
