"""
Secrets helper - fetches API keys from AWS Secrets Manager with caching.
"""
import json
import os
import boto3
from functools import lru_cache

_client = None
_cache: dict[str, dict] = {}


def _get_client():
    global _client
    if _client is None:
        region = os.environ.get("AWS_REGION", "ap-northeast-1")
        _client = boto3.client("secretsmanager", region_name=region)
    return _client


def get_secret(secret_name: str, key: str | None = None) -> str:
    """Secrets Managerからシークレットを取得する（Lambda実行中はキャッシュ）。

    Args:
        secret_name: シークレット名 (e.g. "ars/rakuten", "ars/hotpepper/api-key")
        key: JSON形式の場合のキー名。Noneならプレーンテキストとして返す。

    Returns:
        シークレット値。取得失敗時は空文字列。
    """
    if secret_name in _cache:
        secret_data = _cache[secret_name]
    else:
        try:
            client = _get_client()
            resp = client.get_secret_value(SecretId=secret_name)
            secret_string = resp.get("SecretString", "")

            # JSON形式かプレーンテキストか判定
            try:
                secret_data = json.loads(secret_string)
            except (json.JSONDecodeError, TypeError):
                secret_data = {"_plain": secret_string}

            _cache[secret_name] = secret_data
        except Exception as e:
            print(f"Failed to get secret '{secret_name}': {e}")
            return ""

    if key:
        return str(secret_data.get(key, ""))
    else:
        # プレーンテキストの場合
        if "_plain" in secret_data:
            return secret_data["_plain"]
        # JSONの場合は最初の値を返す
        values = [v for k, v in secret_data.items() if not k.startswith("_")]
        return str(values[0]) if values else ""
