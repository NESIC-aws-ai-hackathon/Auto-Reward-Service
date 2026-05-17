"""
DynamoDB サービス — ArsTable への全 CRUD 操作

設計方針:
- ArsTable への単一窓口
- boto3 ClientError を DynamoDBError に変換して上位へ伝播
- モジュールレベルシングルトンパターン（コールドスタート後の接続再利用）
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from utils.exceptions import DynamoDBError
from utils.logger import get_logger

logger = get_logger(__name__)


class DynamoDBService:
    """ArsTable への CRUD + GSI クエリを提供するサービスクラス"""

    def __init__(self, table_name: str = None) -> None:
        self.table_name = table_name or os.environ["TABLE_NAME"]
        self._resource = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
        )
        self._table = self._resource.Table(self.table_name)

    # ─────────────────────────────────────────
    # 基本 CRUD
    # ─────────────────────────────────────────

    def put_item(self, pk: str, sk: str, item: dict[str, Any]) -> None:
        """アイテムを作成・上書きする"""
        data = _sanitize_floats(dict(item))
        data["PK"] = pk
        data["SK"] = sk
        try:
            self._table.put_item(Item=data)
            logger.debug("put_item success", pk=pk, sk=sk)
        except ClientError as e:
            raise DynamoDBError(f"put_item 失敗: PK={pk}, SK={sk}", e) from e

    def get_item(self, pk: str, sk: str) -> Optional[dict[str, Any]]:
        """GetItem — 存在しない場合は None を返す"""
        try:
            response = self._table.get_item(Key={"PK": pk, "SK": sk})
            return response.get("Item")
        except ClientError as e:
            raise DynamoDBError(f"get_item 失敗: PK={pk}, SK={sk}", e) from e

    def query_by_pk(
        self,
        pk: str,
        sk_prefix: str = None,
        limit: int = None,
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        """PK + SK プレフィックスでクエリする

        Args:
            pk: パーティションキー
            sk_prefix: SK の先頭一致フィルタ（None の場合は PK のみ）
            limit: 取得会数の上限（None の場合は制限なし）
            descending: True の場合は SK 降順（最新順）
        """
        try:
            if sk_prefix:
                key_condition = Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
            else:
                key_condition = Key("PK").eq(pk)

            kwargs: dict[str, Any] = {
                "KeyConditionExpression": key_condition,
                "ScanIndexForward": not descending,
            }
            if limit is not None:
                kwargs["Limit"] = limit

            response = self._table.query(**kwargs)
            return response.get("Items", [])
        except ClientError as e:
            raise DynamoDBError(
                f"query_by_pk 失敗: PK={pk}, sk_prefix={sk_prefix}", e
            ) from e

    def update_item(self, pk: str, sk: str, updates: dict[str, Any]) -> None:
        """部分更新（UpdateExpression を動的生成）"""
        if not updates:
            return

        expression_parts: list[str] = []
        expression_names: dict[str, str] = {}
        expression_values: dict[str, Any] = {}

        for i, (key, value) in enumerate(updates.items()):
            name_key = f"#k{i}"
            value_key = f":v{i}"
            expression_parts.append(f"{name_key} = {value_key}")
            expression_names[name_key] = key
            expression_values[value_key] = value

        update_expression = "SET " + ", ".join(expression_parts)

        try:
            self._table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
            )
            logger.debug("update_item success", pk=pk, sk=sk)
        except ClientError as e:
            raise DynamoDBError(f"update_item 失敗: PK={pk}, SK={sk}", e) from e

    def delete_item(self, pk: str, sk: str) -> None:
        """アイテムを削除する"""
        try:
            self._table.delete_item(Key={"PK": pk, "SK": sk})
            logger.debug("delete_item success", pk=pk, sk=sk)
        except ClientError as e:
            raise DynamoDBError(f"delete_item 失敗: PK={pk}, SK={sk}", e) from e

    def increment_atomic_counter(
        self,
        pk: str,
        sk: str,
        attribute: str = "count",
        ttl: int = None,
    ) -> int:
        """アトミックにカウンタを +1 し、更新後の値を返す

        DynamoDB UpdateItem の ADD 演算子を使用するため、
        Lambda の並行実行においてもカウントの整合性が保たれる。

        Args:
            pk: PK 値
            sk: SK 値
            attribute: インクリメントする数値属性名
            ttl: アイテムが存在しない場合に設定する TTL（Unix タイムスタンプ）

        Returns:
            更新後のカウント値（int）
        """
        update_expr = "ADD #cnt :one"
        expr_names = {"#cnt": attribute}
        expr_values: dict[str, Any] = {":one": 1}

        if ttl is not None:
            update_expr += " SET #ttl = if_not_exists(#ttl, :ttl)"
            expr_names["#ttl"] = "ttl"
            expr_values[":ttl"] = ttl

        try:
            response = self._table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="UPDATED_NEW",
            )
            count = response.get("Attributes", {}).get(attribute, 1)
            logger.debug("increment_atomic_counter success", pk=pk, sk=sk, count=int(count))
            return int(count)
        except ClientError as e:
            raise DynamoDBError(f"increment_atomic_counter 失敗: PK={pk}, SK={sk}", e) from e

    def add_to_monthly_summary(
        self,
        pk: str,
        month_sk: str,
        amount: int,
        reward_budget: int,
        updated_at: str,
    ) -> dict:
        """月次支出累計にアトミック加算する（ADD 演算子）

        初回は reward_budget を if_not_exists で設定する。

        Returns:
            更新後のアイテム属性
        """
        try:
            response = self._table.update_item(
                Key={"PK": pk, "SK": month_sk},
                UpdateExpression=(
                    "ADD #amt :amt, #cnt :one "
                    "SET #rb = if_not_exists(#rb, :rb), #ua = :ua"
                ),
                ExpressionAttributeNames={
                    "#amt": "total_amount",
                    "#cnt": "expense_count",
                    "#rb": "reward_budget",
                    "#ua": "updated_at",
                },
                ExpressionAttributeValues={
                    ":amt": amount,
                    ":one": 1,
                    ":rb": reward_budget,
                    ":ua": updated_at,
                },
                ReturnValues="ALL_NEW",
            )
            logger.debug("add_to_monthly_summary success", pk=pk, month_sk=month_sk, amount=amount)
            return response.get("Attributes", {})
        except ClientError as e:
            raise DynamoDBError(
                f"add_to_monthly_summary 失敗: PK={pk}, SK={month_sk}", e
            ) from e

    # ─────────────────────────────────────────
    # GSI クエリ
    # ─────────────────────────────────────────

    def query_by_gsi(
        self,
        entity_type: str,
        filter_expr: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        """
        entityType-index GSI でクエリする

        対象: PROFILE / PREF_MEMORY エンティティのみ

        Args:
            entity_type: GSI PK 値（例: "PROFILE", "PREF_MEMORY"）
            filter_expr: 追加フィルタ dict（例: {"status": "ACTIVE"}）

        Returns:
            アイテムリスト
        """
        try:
            kwargs: dict[str, Any] = {
                "IndexName": "entityType-index",
                "KeyConditionExpression": Key("entityType").eq(entity_type),
            }

            if filter_expr:
                condition = None
                for k, v in filter_expr.items():
                    attr_cond = Attr(k).eq(v)
                    condition = attr_cond if condition is None else condition & attr_cond
                kwargs["FilterExpression"] = condition

            response = self._table.query(**kwargs)
            return response.get("Items", [])
        except ClientError as e:
            raise DynamoDBError(
                f"query_by_gsi 失敗: entity_type={entity_type}", e
            ) from e


# ─────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────

def _sanitize_floats(obj: Any) -> Any:
    """boto3 DynamoDB リソース API は float 非対応のため Decimal に変換する。

    dict / list を再帰的に処理し、float を Decimal(str(v)) に変換する。
    None, str, int, bool, Decimal はそのまま返す。
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


# ─────────────────────────────────────────
# モジュールレベルシングルトン
# ─────────────────────────────────────────
_instance: Optional[DynamoDBService] = None


def get_dynamodb_service() -> DynamoDBService:
    """DynamoDBService シングルトンを返す（コールドスタート後の接続再利用）"""
    global _instance
    if _instance is None:
        _instance = DynamoDBService()
    return _instance
