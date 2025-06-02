import subprocess
import os
import sys
import ctypes
from .main import main as run_main 

python = sys.executable
main_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))

# 起動通知（ポップアップ）
ctypes.windll.user32.MessageBoxW(
    0,
    f"KeiriWatcher をバックグラウンドで起動しました。\n\n{main_script}",
    "📂 起動完了",
    0x40
)

# コマンド文字列を明示的に組み立て（start "" の""を省略）
cmd = f'start /B "" "{python}" "{main_script}"'

# 実行（shell=True で解釈させる）
subprocess.Popen(cmd, shell=True)
