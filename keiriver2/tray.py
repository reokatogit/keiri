# tray.py

import os
import sys
import threading
import tkinter as tk
from pystray import Icon, Menu, MenuItem
from PIL import Image
from watch_folder import run_batch_watcher_loop, stop_batch_watcher
from get_api_key import get_openai_api_key
from settings import SettingsDialog

# 監視用スレッドをグローバルで保持
watcher_thread: threading.Thread | None = None

def start_watcher():
    """監視スレッドを立ち上げ"""
    global watcher_thread
    if watcher_thread and watcher_thread.is_alive():
        return
    stop_batch_watcher()  # 停止フラグクリア
    watcher_thread = threading.Thread(
        target=run_batch_watcher_loop,
        daemon=True
    )
    watcher_thread.start()

def stop_watcher():
    """監視ループ停止をシグナル"""
    stop_batch_watcher()

def open_log():
    """ログファイルを開く"""
    log_path = os.path.join("log", "watch_folder.log")
    if os.path.exists(log_path):
        os.system(f'notepad "{log_path}"')
    else:
        os.system('echo ログがまだありません > temp_log.txt && notepad temp_log.txt')

def on_open_settings(icon, item):
    """設定ウィンドウを表示"""
    root = tk.Tk()
    root.withdraw()
    SettingsDialog(root)
    root.destroy()
    icon.update_menu()

def restart_app(icon, item):
    """アプリを再起動"""
    stop_watcher()
    icon.stop()
    # 同じインタプリタ＋引数で再起動
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def quit_app(icon, item):
    """完全終了"""
    stop_watcher()
    icon.stop()
    sys.exit(0)

def show_tray_icon():
    # 起動時に API キーを確保
    try:
        get_openai_api_key()
    except Exception as e:
        print(f"[ERROR] APIキー取得失敗: {e}")

    # 自動で監視を開始
    start_watcher()

    # アイコン読み込み
    ico_path = os.path.abspath("icon.ico")
    try:
        icon_image = Image.open(ico_path)
    except Exception as e:
        print(f"[WARN] アイコン読み込み失敗: {e}")
        icon_image = Image.new('RGB', (64, 64), (255, 0, 0))

    # メニューを動的に作成
    def make_menu():
        running = watcher_thread and watcher_thread.is_alive()
        return Menu(
            MenuItem("📝ログを見る", lambda i, _: open_log()),
            MenuItem("⚙️設定", on_open_settings),
            MenuItem("🔄再起動", restart_app),
            MenuItem("❌終了", quit_app)
        )

    icon = Icon("keiri_system", icon_image, "帳簿アップロード監視", menu=make_menu())
    icon.run()
