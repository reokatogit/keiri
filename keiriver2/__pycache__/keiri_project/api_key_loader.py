import os
import tkinter as tk
from tkinter import simpledialog, messagebox
from keiri_project.config import API_KEY_PATH

def is_api_key_valid(api_key: str) -> bool:
    import openai
    try:
        openai.api_key = api_key
        openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1
        )
        return True
    except openai.error.AuthenticationError:
        return False
    except Exception:
        return False

def get_openai_api_key() -> str:
    if os.path.exists(API_KEY_PATH):
        with open(API_KEY_PATH, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if key:
                return key

    root = tk.Tk()
    root.withdraw()

    while True:
        # カスタムダイアログ作成
        dialog = tk.Toplevel()
        dialog.title("🔑 APIキーの入力")
        dialog.geometry("400x180")
        dialog.resizable(False, False)

        tk.Label(dialog, text="OpenAIのAPIキーを入力してください 😊", pady=10).pack()

        entry = tk.Entry(dialog, width=50, show="*")
        entry.pack(pady=5)

        result = {"status": None, "key": ""}

        def on_submit():
            result["status"] = "submit"
            result["key"] = entry.get().strip()
            dialog.destroy()

        def on_skip():
            result["status"] = "skip"
            dialog.destroy()

        tk.Button(dialog, text="補完を有効にする", command=on_submit).pack(pady=5)
        tk.Button(dialog, text="キーなしで始める", command=on_skip).pack()

        dialog.transient(root)
        dialog.grab_set()
        root.wait_window(dialog)

        if result["status"] == "skip":
            messagebox.showinfo("補完はスキップされます", "APIキーなしでスタートします！")
            return ""

        if result["status"] == "submit":
            key = result["key"]
            if not key:
                messagebox.showinfo("入力がありません", "APIキーを入力するか、キーなしで始めるを選んでください！")
                continue
            if is_api_key_valid(key):
                with open(API_KEY_PATH, 'w', encoding='utf-8') as f:
                    f.write(key)
                messagebox.showinfo("✅ APIキー設定完了", "補完が有効になりました！")
                return key
            else:
                messagebox.showwarning("❌ 無効なAPIキー", "APIキーが正しくないようです。\nもう一度入力してください！")
