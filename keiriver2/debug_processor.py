# keiriver2/debug_processor.py

import os
import sys
from parser import parse_filename
from config import WATCH_DIR, PROCESSED_DIR, VALID_EXTENSIONS

def handle_new_file(filepath: str) -> None:
    print(f">>> 入力ファイル: {filepath}")
    print("存在チェック:", os.path.exists(filepath))
    meta = parse_filename(filepath)
    print(f"[DEBUG] meta: {meta}")

    if 'エラー' in meta:
        print(f"[ERROR] ファイル名解析失敗: {meta['エラー']}")
        return

    dept = meta['部署']
    ym   = meta['年月']
    print(f"[REGEN] 部署={dept} 年月={ym}")

    # WATCH_DIR
    print(f"[DEBUG] WATCH_DIR: {WATCH_DIR}")
    print("→ 存在:", os.path.exists(WATCH_DIR))
    print("→ 中身:", os.listdir(WATCH_DIR))

    # PROCESSED_DIR/<部署>
    proc_dir = os.path.join(PROCESSED_DIR, dept)
    print(f"[DEBUG] PROCESSED_DIR/{dept}: {proc_dir}")
    print("→ 存在:", os.path.isdir(proc_dir))
    if os.path.isdir(proc_dir):
        print("→ 中身:", os.listdir(proc_dir))

    # マッチテスト
    candidates = []
    for fn in os.listdir(WATCH_DIR):
        low = fn.lower()
        if low.endswith(tuple(VALID_EXTENSIONS)) and (ym in fn or f"{int(ym.split('-')[1])}月" in fn):
            candidates.append(fn)
    print(f"[DEBUG] WATCH_DIR マッチ候補: {candidates}")

    if os.path.isdir(proc_dir):
        for fn in os.listdir(proc_dir):
            low = fn.lower()
            if low.endswith(tuple(VALID_EXTENSIONS)) and (ym in fn or f"{int(ym.split('-')[1])}月" in fn):
                candidates.append(f"{dept}/{fn}")
    print(f"[DEBUG] 合計マッチ候補: {candidates}")

    if not candidates:
        print(f"[WARN] raw ファイルが見つかりません (部署={dept}, 年月={ym})")
    else:
        print(f"[OK] {len(candidates)} 件見つかりました")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python debug_processor.py <path/to/file.xlsx>")
        sys.exit(1)
    for path in sys.argv[1:]:
        handle_new_file(path)
