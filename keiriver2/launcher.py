import subprocess
import os
import sys

#VSCodeやWindows起動時に launcher.py をショートカットに登録すれば、常時バックグラウンド監視が可能

def launch_background():
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(__file__), 'main.py')

    # Windows用：非表示でバックグラウンド実行
    DETACHED_PROCESS = 0x00000008
    subprocess.Popen([python_exe, script_path],
                     creationflags=DETACHED_PROCESS,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)

if __name__ == '__main__':
    launch_background()
