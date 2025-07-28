# notifier.py
from win10toast import ToastNotifier
import os

# 通知に使うアイコンファイル（owl.ico をプロジェクト直下に置く想定）
ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.ico")

toaster = ToastNotifier()

def notify(title: str, msg: str, duration: int = 5):
    """
    右下通知を出します。
    title: 通知タイトル（例："Keiri 処理完了"）
    msg:  通知メッセージ
    duration: 秒数
    """
    # icon_path オプションでアイコンを指定
    toaster.show_toast(
        title,
        msg,
        icon_path=ICON_PATH,
        duration=duration,
        threaded=True
    )
