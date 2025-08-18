# dynamodb_mapping_store.py
# DynamoDB用 mapping_storeインターフェース雛形
import boto3
import os
from typing import Optional
from datetime import datetime

table_name = os.environ.get('DYNAMODB_MAPPING_TABLE', 'mapping_store')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(table_name)

def ensure_schema():
    pass

def load_mapping_store() -> dict[str, str]:
    resp = table.scan()
    return {item['cleaned']: item['normalized'] for item in resp.get('Items', [])}

def append_mapping(cleaned: str, normalized: str, field_name: str) -> None:
    now = datetime.utcnow().isoformat()
    table.put_item(Item={
        'cleaned': cleaned,
        'normalized': normalized,
        'field_name': field_name,
        'created_at': now
    })
