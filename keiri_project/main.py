import os
import time
from watchdog.observers import Observer
from .file_watcher import FolderHandler
from .config import TEMP_ROOT, OUTPUT_ROOT, WATCH_DIR
from .processor import start_merge_summary_watcher

print("✅ main.py 開始")
print(f"TEMP_ROOT = {TEMP_ROOT}")
print(f"OUTPUT_ROOT = {OUTPUT_ROOT}")
print(f"WATCH_DIR = {WATCH_DIR}")
if __name__ == "__main__":
    print("main.py if __name__ == '__main__' に入った")

if __name__ == "__main__":
    # 一時フォルダ・出力フォルダを作成
    os.makedirs(TEMP_ROOT, exist_ok=True)
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    # ✅ 統合summary監視スレッドを起動
    start_merge_summary_watcher()

    # フォルダ監視開始
    observer = Observer()
    observer.schedule(FolderHandler(), path=WATCH_DIR, recursive=False)
    observer.start()
    print(f"📂 Watching folder: {WATCH_DIR}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Ctrl+C で停止
        observer.stop()
        print("🛑 Watching stopped")
    observer.join()