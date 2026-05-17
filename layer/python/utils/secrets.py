"""
AWS Secrets Manager から秘匿値を取得するユーティリティ

設計方針:
- シークレットは LINE / Google / Rakuten / HotPepper の 4 つに分割保管
- 各シークレットをモジュールレベルでキャッシュ（コールドスタート後のウォームインボケーションで再利用）
- キャッシュキー = シークレット名（env var の値）

環境変数:
  LINE_SECRET_NAME       - ars/line        (LINE_CHANNEL_SECRET, LINE_ACCESS_TOKEN)
  GOOGLE_SECRET_NAME     - ars/google      (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
  RAKUTEN_SECRET_NAME    - ars/rakuten     (RAKUTEN_APP_ID)
  HOTPEPPER_SECRET_NAME  - ars/hotpepper/api-key  (HOTPEPPER_API_KEY)
"""
from __future__ import annotations

import json
import os

import boto3
from botocore.exceptions import ClientError

from utils.exceptions import SecretsError

_cache: dict[str, dict] = {}


def _get_boto_client():
    """Secrets Manager クライアントを返す（テスト時のモック差し替え用に分離）"""
    return boto3.client(
        "secretsmanager",
        region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
    )


def get_secret(secret_name: str) -> dict:
    """
    指定されたシークレット名の値を返す（モジュールレベルキャッシュ）

    Args:
        secret_name: Secrets Manager のシークレット名

    Returns:
        シークレット値の dict

    Raises:
        SecretsError: 取得失敗時
    """
    if secret_name in _cache:
        return _cache[secret_name]

    try:
        client = _get_boto_client()
        response = client.get_secret_value(SecretId=secret_name)
        _cache[secret_name] = json.loads(response["SecretString"])
        return _cache[secret_name]
    except ClientError as e:
        raise SecretsError(
            f"Secrets Manager からの取得に失敗しました: {secret_name}", e
        ) from e


def get_line_secrets() -> dict:
    """LINE シークレット (LINE_CHANNEL_SECRET, LINE_ACCESS_TOKEN) を返す"""
    return get_secret(os.environ["LINE_SECRET_NAME"])


def get_google_secrets() -> dict:
    """Google OAuth シークレット (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) を返す"""
    return get_secret(os.environ["GOOGLE_SECRET_NAME"])


def get_rakuten_secrets() -> dict:
    """楽天 API シークレット (RAKUTEN_APP_ID) を返す"""
    return get_secret(os.environ["RAKUTEN_SECRET_NAME"])


def get_hotpepper_secrets() -> dict:
    """ホットペッパー API シークレット (HOTPEPPER_API_KEY) を返す"""
    return get_secret(os.environ["HOTPEPPER_SECRET_NAME"])


def clear_cache() -> None:
    """キャッシュをクリアする（テスト用）"""
    _cache.clear()
