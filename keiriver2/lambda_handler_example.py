# lambda_handler_example.py
# Lambdaハンドラ雛形
import json
from processor import handle_new_file

def lambda_handler(event, context):
    # S3イベント等からファイルパス取得
    file_path = event.get('file_path')
    if not file_path:
        return {'statusCode': 400, 'body': 'file_path missing'}
    handle_new_file(file_path)
    return {'statusCode': 200, 'body': 'OK'}
