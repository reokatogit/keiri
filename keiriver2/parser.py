import os
import re
from datetime import datetime

def parse_filename(filename):
    """
    ファイル名から部署名・元請け企業名・年月を抽出する。
    形式例: '営業部_株式会社Forneeds_2025年1月.xlsx'
    """
    name = os.path.basename(filename)
    name = os.path.splitext(name)[0]

    pattern = r'(.+?)_(.+?)_(\d{4})年(\d{1,2})月'
    match = re.match(pattern, name)

    if match:
        department = match.group(1)
        client = match.group(2)
        year = int(match.group(3))
        month = int(match.group(4))
        return {
            '部署': department,
            '元請け': client,
            '年': year,
            '月': month,
            '年月': f"{year}-{month:02d}"
        }
    else:
        return {
            'エラー': f"ファイル名形式不正: {name}"
        }
