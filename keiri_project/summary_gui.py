import tkinter as tk
from tkinter import messagebox
import subprocess
import os

def run_merge_script():
    try:
        # スクリプト実行（Windows想定）
        result = subprocess.run(
            ["python", "merge_summaries.py"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            messagebox.showinfo("完了", "統合レポートと部署集計を出力しました。")
        else:
            messagebox.showerror("エラー", f"実行中にエラーが発生しました：\n{result.stderr}")
    except Exception as e:
        messagebox.showerror("エラー", f"スクリプトの実行に失敗しました：\n{e}")

# GUIウィンドウ作成
root = tk.Tk()
root.title("集計レポート作成ツール")
root.geometry("360x160")

label = tk.Label(root, text="📊 出力済みのsummaryを統合して\n全社レポートと部署別集計を作成します", pady=20)
label.pack()

btn = tk.Button(root, text="統合レポートを作成", command=run_merge_script, bg="#4CAF50", fg="white", height=2, width=25)
btn.pack()

root.mainloop()
