# dynamodb_customer.py
# DynamoDB用 顧客レジストリインターフェース雛形
import boto3
import os
from typing import Optional
from datetime import datetime

table_name = os.environ.get('DYNAMODB_CUSTOMER_TABLE', 'customer_registry')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(table_name)

def ensure_schema():
    # DynamoDBはスキーマレスなので不要
    pass

def get_first_seen(store_name: str) -> Optional[str]:
    resp = table.get_item(Key={'store_name': store_name})
    item = resp.get('Item')
    return item['first_seen_ym'] if item else None

def upsert_first_seen(store_name: str, ym: str) -> None:
    now = datetime.utcnow().isoformat()
    # 既存値より古い場合のみ更新
    resp = table.get_item(Key={'store_name': store_name})
    item = resp.get('Item')
    if not item or ym < item['first_seen_ym']:
        table.put_item(Item={
            'store_name': store_name,
            'first_seen_ym': ym,
            'created_at': now
        })
