import time
import os
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from keiri_project.parser import parse_filename
from keiri_project.processor import process_group
from keiri_project.config import WATCH_DIR, TEMP_ROOT

processed_files = {}

class FolderHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        fp = event.src_path
        if not fp.lower().endswith((".csv", ".xlsx", ".xls")) or os.path.basename(fp).startswith("~$"):
            return
        now = time.time()
        if processed_files.get(fp) and now - processed_files[fp] < 10:
            return
        processed_files[fp] = now
        dept, yyyymm = parse_filename(fp)
        if '不明' in (dept, yyyymm):
            return
        dst = os.path.join(TEMP_ROOT, dept, yyyymm)
        os.makedirs(dst, exist_ok=True)
        shutil.copy(fp, os.path.join(dst, os.path.basename(fp)))
        process_group(dept, yyyymm)

    def on_deleted(self, event):
        if event.is_directory:
            return
        fp = event.src_path
        if not fp.lower().endswith((".csv", ".xlsx", ".xls")):
            return
        dept, yyyymm = parse_filename(fp)
        if '不明' in (dept, yyyymm):
            return
        temp_f = os.path.join(TEMP_ROOT, dept, yyyymm, os.path.basename(fp))
        if os.path.exists(temp_f):
            os.remove(temp_f)
        process_group(dept, yyyymm)
