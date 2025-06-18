import os 
import time
from watchdog.observers import Observer
from keiri_project.file_watcher import FolderHandler
from keiri_project.config import TEMP_ROOT, OUTPUT_ROOT, WATCH_DIR
from keiri_project.processor import handle_new_file  

print("ddd")
def process_existing_files():
    for fname in os.listdir(WATCH_DIR):
        fpath = os.path.join(WATCH_DIR, fname)
        if os.path.isfile(fpath):
            print(f"🔁 起動時に処理: {fpath}")
            handle_new_file(fpath)

print(f"📌 __name__ = {__name__}")

if __name__ == "__main__":
    print("✅ main.py 開始")
    print(f"TEMP_ROOT = {TEMP_ROOT}")
    print(f"OUTPUT_ROOT = {OUTPUT_ROOT}")
    print(f"WATCH_DIR = {WATCH_DIR}")

    os.makedirs(TEMP_ROOT, exist_ok=True)
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    process_existing_files()

    observer = Observer()
    observer.schedule(FolderHandler(), path=WATCH_DIR, recursive=False)
    observer.start()
    print(f"📂 Watching folder: {WATCH_DIR}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("🛑 Watching stopped")
    observer.join()
