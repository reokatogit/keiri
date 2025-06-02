import os
import pandas as pd
import glob

SUMMARY_DIR = "output"
REPORT_DIR = "report"
MERGED_NAME = "統合_summary"
DEPT_SUMMARY_NAME = "部署別_summary"

def parse_filename(filename):
    base = os.path.splitext(filename)[0]
    parts = base.split("_")
    if len(parts) >= 2:
        dept = parts[0]
        yyyymm = ''.join(filter(str.isdigit, parts[1]))
    else:
        dept, yyyymm = "不明", "不明"
    return dept, yyyymm

def merge_and_aggregate():
    merged_dfs = []

    if not os.path.exists(SUMMARY_DIR):
        print("summaryディレクトリが存在しません。")
        return

    # 🔍 サブディレクトリも含めて summary.csv を再帰的に探索
    summary_files = glob.glob(os.path.join(SUMMARY_DIR, "**/summary.csv"), recursive=True)

    if not summary_files:
        print("統合対象の summary.csv が見つかりませんでした。")
        return

    for path in summary_files:
        try:
            df = pd.read_csv(path)
            # ディレクトリ構造から dept / yyyymm を抽出
            rel_path = os.path.relpath(path, SUMMARY_DIR)
            parts = rel_path.split(os.sep)
            if len(parts) >= 2:
                dept = parts[0]
                yyyymm = parts[1]
            else:
                dept, yyyymm = "不明", "不明"
            df.insert(0, "部署", dept)
            df.insert(1, "年月", yyyymm)
            merged_dfs.append(df)
            print(f"統合対象: {path}")
        except Exception as e:
            print(f"読み込み失敗: {path} → {e}")

    os.makedirs(REPORT_DIR, exist_ok=True)

    merged_df = pd.concat(merged_dfs, ignore_index=True)
    merged_path_csv = os.path.join(REPORT_DIR, f"{MERGED_NAME}.csv")
    merged_path_xlsx = os.path.join(REPORT_DIR, f"{MERGED_NAME}.xlsx")
    merged_df.to_csv(merged_path_csv, index=False)
    merged_df.to_excel(merged_path_xlsx, index=False)
    print(f"📦 統合summary出力: {merged_path_csv} / {merged_path_xlsx}")

    # ✅ 部署別 summary 作成
    dept_summary = merged_df.groupby(["年月", "部署"])["合計金額"].sum().reset_index()
    dept_summary.columns = ["年月", "部署", "部署別合計金額"]

    dept_path_csv = os.path.join(REPORT_DIR, f"{DEPT_SUMMARY_NAME}.csv")
    dept_path_xlsx = os.path.join(REPORT_DIR, f"{DEPT_SUMMARY_NAME}.xlsx")
    dept_summary.to_csv(dept_path_csv, index=False)
    dept_summary.to_excel(dept_path_xlsx, index=False)
    print(f"部署別summary出力: {dept_path_csv} / {dept_path_xlsx}")

if __name__ == "__main__":
    print("summary統合処理を開始します...")
    merge_and_aggregate()
    print("処理完了")