#このコードは簡易データ成型用スクリプトです。
#目的は飲食店名の標準化と売上データの名寄せを行うことです。
#keiri_projectとは違うモノ

import pandas as pd
import re
import jaconv
import os

# ==== 飲食店名標準化関数（強化版） ====
def standardize_store_name(name):
    if not isinstance(name, str):
        return ""

    # ひらがな→カタカナ
    name = jaconv.hira2kata(name)
    # 半角化（数字・英字）
    name = jaconv.z2h(name, kana=False, digit=True, ascii=True)
    # 小文字化
    name = name.lower()
    # 空白除去
    name = re.sub(r'\s+', '', name)
    # カッコ類除去
    name = re.sub(r'[（）()「」『』\[\]【】]', '', name)
    # 店舗表現除去（"店", "本店", など）
    name = re.sub(r'店|店舗|支店|本店|支社|営業所', '', name)
    # 記号除去
    name = re.sub(r'ー|‐|―|-|–|−', '', name)
    name = re.sub(r'＆|&|・|／|/|\.', '', name)

    # 表記ゆれ対応（略称 → 正式名）
    replacements = {
        "マック": "マクドナルド",
        "ケンタ": "ケンタッキーフライドチキン",
        "モス": "モスバーガー",
        "すき家": "すきや",
        "吉牛": "吉野家"
    }
    for short, full in replacements.items():
        name = name.replace(short, full)

    # 語順を並び替え（空白で分割してソート）
    words = re.split(r'\s+', name)
    name = ''.join(sorted(words))
    return name

# ==== ファイルパス ====
sales_path = "data/lifestyle_sales_20250430.xlsx"
approach_path = "data/approach_list_20250527.xlsx"

# ==== データ読み込み ====
df_sales = pd.read_excel(sales_path, sheet_name="月次【売上】", usecols="I,O")
df_sales.columns = ["店舗名", "金額"]
df_sales = df_sales[df_sales["金額"] != 0].copy()

df_approach = pd.read_excel(approach_path, sheet_name="Sheet1", usecols="C,M,N,O,P,Q,R")
df_approach.columns = ["店舗名", "M", "N", "O", "P", "Q", "R"]

# ==== 名寄せキー作成 ====
df_sales["キー"] = df_sales["店舗名"].apply(standardize_store_name)
df_approach["キー"] = df_approach["店舗名"].apply(standardize_store_name)

# ==== 照合 ====
merged = df_sales.merge(df_approach.drop(columns=["店舗名"]), on="キー", how="left")

# ==== 結果分割 ====
matched = merged[merged[["M", "N", "O", "P", "Q", "R"]].notna().any(axis=1)]
unmatched = merged[merged[["M", "N", "O", "P", "Q", "R"]].isna().all(axis=1)]

# ==== 出力ディレクトリ作成 ====
os.makedirs("results", exist_ok=True)


# ==== 結果保存 ====
matched.to_excel("results/matched_results.xlsx", index=False)
unmatched.to_excel("results/unmatched_results.xlsx", index=False)

# ==== 完了メッセージ ====
print("✅ 処理完了しました")
print(f"一致：{len(matched)} 件")
print(f"未一致：{len(unmatched)} 件")
print("→ results フォルダに出力しました。")
