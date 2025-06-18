import os
import re
import shutil
import ctypes
from keiri_project.config import WATCH_DIR

def parse_filename(filepath: str):
    base = os.path.basename(filepath)
    name, _ = os.path.splitext(base)
    parts = name.split('_')
    dept = parts[0] if len(parts) > 0 else "不明"
    yyyymm = "不明"
    m = re.search(r"(\d{4})年(\d{1,2})月", name) or re.search(r"(\d{6})", name)
    if m:
        if len(m.groups()) == 2:
            yyyymm = f"{m.group(1)}{m.group(2).zfill(2)}"
        else:
            yyyymm = m.group(1)
    if '不明' in (dept, yyyymm):
        ctypes.windll.user32.MessageBoxW(
            0,
            f"ファイル名:{base}\n部署:{dept}\n年月:{yyyymm}\n形式を確認してください",
            "⚠️ ファイル名ルール不備",
            0x10
        )
        err_dir = os.path.join(WATCH_DIR, "error", "invalid_filename")
        os.makedirs(err_dir, exist_ok=True)
        shutil.move(filepath, os.path.join(err_dir, base))
    return dept, yyyymm
