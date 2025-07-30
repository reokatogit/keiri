# tray.py
import socket
import os, sys, threading, tkinter as tk, csv
import tkinter.messagebox as mb
from pystray import Icon, Menu, MenuItem
from PIL import Image
from watch_folder import run_batch_watcher_loop, stop_batch_watcher
from get_api_key import get_openai_api_key
from settings import SettingsDialog
from config import UNMATCHED_LOG, WATCH_LOG
from mapping_utils import sort_mapping_store 
from win10toast import ToastNotifier            

LOCK_PORT = 39393
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    sys.exit(0)

toaster = ToastNotifier()

def on_sort_mapping_store(icon, item):
    try:
        sort_mapping_store()                     
        # 完了通知
        toaster.show_toast(
            "辞書ソート完了",
            "mapping_store.csv を並び替えました。",
            icon_path=None, duration=3, threaded=True
        )
    except Exception as e:
        mb.showerror("ソート失敗", f"辞書のソートに失敗しました：\n{e}")
watcher_thread: threading.Thread | None = None

def start_watcher():
    global watcher_thread
    if watcher_thread and watcher_thread.is_alive():
        return
    stop_batch_watcher()
    watcher_thread = threading.Thread(target=run_batch_watcher_loop, daemon=True)
    watcher_thread.start()

def stop_watcher():
    stop_batch_watcher()

def open_log():
    if os.path.exists(WATCH_LOG):
        os.system(f'notepad "{WATCH_LOG}"')
    else:
        os.system('echo ログがまだありません > temp_log.txt && notepad temp_log.txt')

def clear_logs():
    # CSVログ（ヘッダーのみ残す）
    if os.path.exists(UNMATCHED_LOG):
        with open(UNMATCHED_LOG, 'r', encoding='utf-8-sig', newline='') as f:
            header = next(csv.reader(f), None)
        with open(UNMATCHED_LOG, 'w', encoding='utf-8-sig', newline='') as f:
            if header:
                csv.writer(f).writerow(header)
    # テキストログを空に
    if os.path.exists(WATCH_LOG):
        open(WATCH_LOG, 'w', encoding='utf-8').close()
    mb.showinfo("ログクリア完了", "ログがクリアされました。")

def on_open_settings(icon, item):
    root = tk.Tk(); root.withdraw()
    SettingsDialog(root)
    root.destroy()
    icon.update_menu()

def restart_app(icon, item):
    stop_watcher(); icon.stop()
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def quit_app(icon, item):
    stop_watcher(); icon.stop()
    sys.exit(0)

def show_tray_icon():
    # APIキー取得→監視開始
    try: get_openai_api_key()
    except Exception as e: print(f"[ERROR] APIキー取得失敗: {e}")
    start_watcher()

    # アイコン読み込み
    ico_path = os.path.abspath("icon.ico")
    try: icon_image = Image.open(ico_path)
    except Exception as e:
        print(f"[WARN] アイコン読み込み失敗: {e}")
        icon_image = Image.new('RGB', (64,64), (255,0,0))

    # メニュー定義
    menu = Menu(
        MenuItem("📝ログを見る", lambda i, _: open_log()),
        MenuItem("🗑️ログをクリア", lambda i, _: clear_logs()),
        MenuItem("⚙️設定", on_open_settings),
        MenuItem("🔃辞書をソート", on_sort_mapping_store),
        MenuItem("🔄再起動", restart_app),
        MenuItem("❌終了", quit_app),
    )
    icon = Icon("keiri_system", icon_image, "帳簿アップロード監視", menu=menu)
    icon.run()
