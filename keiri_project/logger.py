import os
import pandas as pd
import ctypes
from datetime import datetime

unmatched_popup_shown = False
unmatched_count = 0
from keiri_project.config import API_KEY_PATH # adjust if needed


def show_popup_warning(message: str, title: str = "⚠️ 警告"):
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)


def log_unmatched(raw: str, source_file: str, column: str, output_dir: str, reason: str = "補完失敗"):
    global unmatched_popup_shown, unmatched_count
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "unmatched_final.csv")
    row = pd.DataFrame([{
        "raw": raw,
        "source_file": os.path.basename(source_file),
        "source_column": column,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    if os.path.exists(log_path):
        row.to_csv(log_path, mode='a', header=False, index=False, encoding='utf-8')
    else:
        row.to_csv(log_path, index=False, encoding='utf-8')
    unmatched_count += 1
    # initial popup
    if not unmatched_popup_shown:
        show_popup_warning(
            f"名寄せできなかった値が存在します。\n→ unmatched_final.csv を確認してください。",
            title="⚠️ 名寄せ未一致あり"
        )
        unmatched_popup_shown = True


def finalize_unmatched(output_dir: str):
    global unmatched_count, unmatched_popup_shown
    if unmatched_count > 0:
        show_popup_warning(
            f"この処理で名寄せできなかった値が {unmatched_count} 件ありました。\n→ unmatched_final.csv を確認してください。",
            title="⚠️ 名寄せ未一致件数"
        )
    unmatched_popup_shown = False
    unmatched_count = 0