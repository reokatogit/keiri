from get_api_key import get_openai_api_key
from tray import show_tray_icon
from watch_folder import run_batch_watcher
from tray import show_tray_icon
def main():
    try:
         get_openai_api_key()
    except Exception as e:
         print(f"[ERROR] {e}")
         return

    # 問題なければタスクトレイ＋監視を起動
    
    show_tray_icon()

if __name__ == "__main__":
    main()
