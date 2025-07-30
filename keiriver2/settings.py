# settings.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import keyring
import json
import os
import openai
from config import CONFIG_PATH, CHECK_INTERVAL

class SettingsDialog(simpledialog.Dialog):
    """Tkinter標準のDialogを拡張した設定ウィンドウ"""

    def body(self, master):
        self.title("Keiri システム設定")

        # APIキー
        ttk.Label(master, text="ChatGPT APIキー:").grid(row=0, column=0, sticky="e")
        self.api_var = tk.StringVar()
        self.api_var.set(keyring.get_password("keiri_system", "openai_api_key") or "")
        ttk.Entry(master, textvariable=self.api_var, width=40, show="*").grid(row=0, column=1, padx=5, pady=5)

        # 監視間隔
        ttk.Label(master, text="監視間隔 (秒):").grid(row=1, column=0, sticky="e")
        self.interval_var = tk.IntVar()
        self.interval_var.set(CHECK_INTERVAL)
        ttk.Entry(master, textvariable=self.interval_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # トースト通知のオン／オフ
        #ttk.Label(master, text="トースト通知:").grid(row=2, column=0, sticky="e")
        # トースト通知のオン／オフ（チェックボタンに文言を持たせる）
        #self.notify_var = tk.BooleanVar()
        #cfg = {}
        #if os.path.exists(CONFIG_PATH):
        #    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        #        cfg = json.load(f)
        #self.notify_var.set(cfg.get("toast_notification", True))
        #ttk.Checkbutton(
        #    master,
        #    text="トースト通知を有効にする",
        #    variable=self.notify_var
        #).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    def apply(self):
        # --- 1) APIキー取得 & バリデーション & 保存／削除 ---
        SERVICE = "keiri_system"
        ENTRY   = "openai_api_key"
        key = self.api_var.get().strip()
        if key:
            openai.api_key = key
            try:
                _ = openai.Model.list()
            except Exception as e:
                messagebox.showerror("APIキーエラー", f"APIキーが無効か通信に失敗しました：\n{e}")
                return
            keyring.set_password(SERVICE, ENTRY, key)
        else:
            try:
                keyring.delete_password(SERVICE, ENTRY)
            except keyring.errors.PasswordDeleteError:
                pass


        # 3) 監視間隔のみ保存（トースト通知は常にオン固定）
        cfg = {
            "check_interval": self.interval_var.get()
        }
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        messagebox.showinfo("設定保存", "設定を保存しました。\n再起動後に反映されます。")
