#mapping_utils.py 
import pandas as pd
from pathlib import Path
import os
from config import MAPPING_STORE_PATH

def sort_mapping_store():
    """mapping_store.csv を cleaned カラムでソートして上書き保存"""
    path = Path(MAPPING_STORE_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{path} が見つかりません。")
    df = pd.read_csv(path, encoding='utf-8-sig')
    # ソートキーは 'cleaned'。必要なら別のカラムに変更して下さい
    df = df.sort_values(by='cleaned', ignore_index=True)
    df.to_csv(path, index=False, encoding='utf-8-sig')