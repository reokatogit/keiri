import keyring
import openai

SERVICE = "keiri_system"
ENTRY   = "openai_api_key"

def get_openai_api_key() -> str:
    """
    keyring からシークレットを取得して
    openai.api_key にセットし、返却する。
    未登録ならエラーを投げる。
    """
    key = keyring.get_password(SERVICE, ENTRY)
    if not key:
        raise RuntimeError(
            "APIキーが登録されていません。\n"
        )
    key = keyring.get_password(SERVICE, ENTRY)
    openai.api_key = key
    return key