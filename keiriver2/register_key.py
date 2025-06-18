import keyring
import tkinter as tk
from tkinter import simpledialog, messagebox

SERVICE = "keiri_system"
ENTRY   = "openai_api_key"

def register_api_key():
    root = tk.Tk()
    root.withdraw()
    key = simpledialog.askstring("APIキー登録", "OpenAI API キーを入力してください：", show="*")
    if not key:
        messagebox.showerror("エラー", "キーが入力されませんでした。")
        return
    keyring.set_password(SERVICE, ENTRY, key)
    messagebox.showinfo("完了", "APIキーを登録しました。")

if __name__ == "__main__":
    register_api_key()
