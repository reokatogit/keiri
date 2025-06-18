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
        self.api_var.set(keyring.get_password("keiri", "openai_api_key") or "")
        ttk.Entry(master, textvariable=self.api_var, width=40, show="*").grid(row=0, column=1, padx=5, pady=5)

        # 監視間隔
        ttk.Label(master, text="監視間隔 (秒):").grid(row=1, column=0, sticky="e")
        self.interval_var = tk.IntVar()
        self.interval_var.set(CHECK_INTERVAL)
        ttk.Entry(master, textvariable=self.interval_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # トースト通知のオン／オフ
        ttk.Label(master, text="トースト通知:").grid(row=2, column=0, sticky="e")
        self.notify_var = tk.BooleanVar()
        # 設定ファイルから読み込み
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        self.notify_var.set(cfg.get("toast_notification", True))
        ttk.Checkbutton(master, variable=self.notify_var).grid(row=2, column=1, sticky="w", padx=5, pady=5)

        return master

    def apply(self):
        """OK押下時に呼ばれる：設定を保存"""
        # 1) APIキーのバリデーション
        key = self.api_var.get().strip()
        if key:
            openai.api_key = key
            try:
                # 簡単な接続テスト: モデル一覧を取得
                _ = openai.Model.list()
            except Exception as e:
                messagebox.showerror("APIキーエラー", f"APIキーが無効か通信に失敗しました：\n{e}")
                # ここで保存を中断
                return

        # 2) APIキー保存／削除
        if key:
            keyring.set_password("keiri", "openai_api_key", key)
        else:
            try:
                keyring.delete_password("keiri", "openai_api_key")
            except keyring.errors.PasswordDeleteError:
                pass

        # 3) 監視間隔 & 通知フラグの保存
        cfg = {
            "check_interval": self.interval_var.get(),
            "toast_notification": self.notify_var.get()
        }
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        messagebox.showinfo("設定保存", "設定を保存しました。\n再起動後に反映されます。")
