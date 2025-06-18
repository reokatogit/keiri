import tkinter as tk

root = tk.Tk()
root.title("テストウィンドウ")
root.geometry("300x100")
tk.Label(root, text="これはテストです").pack(pady=20)
root.mainloop()

print("✅ Python実行できてます")
input("終了するにはEnterを押してください")
