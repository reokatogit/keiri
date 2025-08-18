# s3_storage.py
# S3ラッパー関数（ファイル保存・取得）
import boto3
import os

bucket = os.environ.get('S3_BUCKET', 'your-bucket-name')
s3 = boto3.client('s3')

def save_to_storage(key: str, data: bytes):
    s3.put_object(Bucket=bucket, Key=key, Body=data)

def load_from_storage(key: str) -> bytes:
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp['Body'].read()
