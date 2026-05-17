"""dynamodb_service.py のユニットテスト（moto 使用）"""
import pytest
import boto3
from moto import mock_aws

from services.dynamodb_service import DynamoDBService
from utils.exceptions import DynamoDBError


@pytest.fixture
def ddb_table(aws_env):
    """moto で DynamoDB テーブルを作成するフィクスチャ"""
    with mock_aws():
        client = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = client.create_table(
            TableName="ArsTable-test",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "entityType", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "entityType-index",
                    "KeySchema": [
                        {"AttributeName": "entityType", "KeyType": "HASH"},
                        {"AttributeName": "PK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        table.wait_until_exists()
        yield DynamoDBService(table_name="ArsTable-test")


@mock_aws
class TestDynamoDBServiceCRUD:
    def test_put_and_get_item(self, ddb_table):
        ddb_table.put_item(
            pk="USER#U001",
            sk="PROFILE#",
            item={"display_name": "テストユーザー", "status": "ACTIVE"},
        )
        result = ddb_table.get_item(pk="USER#U001", sk="PROFILE#")
        assert result is not None
        assert result["display_name"] == "テストユーザー"
        assert result["PK"] == "USER#U001"
        assert result["SK"] == "PROFILE#"

    def test_get_item_not_found(self, ddb_table):
        result = ddb_table.get_item(pk="USER#NOTEXIST", sk="PROFILE#")
        assert result is None

    def test_update_item(self, ddb_table):
        ddb_table.put_item(
            pk="USER#U001", sk="PROFILE#", item={"status": "ACTIVE"}
        )
        ddb_table.update_item(
            pk="USER#U001", sk="PROFILE#", updates={"status": "INACTIVE"}
        )
        result = ddb_table.get_item(pk="USER#U001", sk="PROFILE#")
        assert result["status"] == "INACTIVE"

    def test_update_item_empty_updates(self, ddb_table):
        # 空の updates は no-op
        ddb_table.put_item(pk="USER#U001", sk="PROFILE#", item={"x": 1})
        ddb_table.update_item(pk="USER#U001", sk="PROFILE#", updates={})
        result = ddb_table.get_item(pk="USER#U001", sk="PROFILE#")
        assert result["x"] == 1

    def test_delete_item(self, ddb_table):
        ddb_table.put_item(pk="USER#U001", sk="PROFILE#", item={})
        ddb_table.delete_item(pk="USER#U001", sk="PROFILE#")
        result = ddb_table.get_item(pk="USER#U001", sk="PROFILE#")
        assert result is None

    def test_query_by_pk(self, ddb_table):
        ddb_table.put_item(pk="USER#U001", sk="CHAT#2026-01-01", item={"role": "user"})
        ddb_table.put_item(pk="USER#U001", sk="CHAT#2026-01-02", item={"role": "assistant"})
        ddb_table.put_item(pk="USER#U001", sk="PROFILE#", item={"status": "ACTIVE"})

        results = ddb_table.query_by_pk(pk="USER#U001", sk_prefix="CHAT#")
        assert len(results) == 2

    def test_query_by_pk_no_prefix(self, ddb_table):
        ddb_table.put_item(pk="USER#U002", sk="PROFILE#", item={})
        ddb_table.put_item(pk="USER#U002", sk="CHAT#2026-01-01", item={})
        results = ddb_table.query_by_pk(pk="USER#U002")
        assert len(results) == 2

    def test_query_by_gsi(self, ddb_table):
        ddb_table.put_item(
            pk="USER#U001",
            sk="PROFILE#",
            item={"entityType": "PROFILE", "status": "ACTIVE"},
        )
        ddb_table.put_item(
            pk="USER#U002",
            sk="PROFILE#",
            item={"entityType": "PROFILE", "status": "INACTIVE"},
        )
        results = ddb_table.query_by_gsi(entity_type="PROFILE")
        assert len(results) == 2

    def test_query_by_gsi_with_filter(self, ddb_table):
        ddb_table.put_item(
            pk="USER#U001",
            sk="PROFILE#",
            item={"entityType": "PROFILE", "status": "ACTIVE"},
        )
        ddb_table.put_item(
            pk="USER#U002",
            sk="PROFILE#",
            item={"entityType": "PROFILE", "status": "INACTIVE"},
        )
        results = ddb_table.query_by_gsi(
            entity_type="PROFILE", filter_expr={"status": "ACTIVE"}
        )
        assert len(results) == 1
        assert results[0]["PK"] == "USER#U001"
