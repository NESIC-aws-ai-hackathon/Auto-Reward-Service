"""
DataAccess Layer - DynamoDB CRUD operations and SK naming conventions.
All SK constants for the entire Unit 8 are defined here.
"""
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key
from shared.config import get_config

# ─── SK Constants (全Unit共通) ───
SK_PROFILE = "PROFILE#"
SK_VOICE_SESSION = "VOICE_SESSION#{session_id}"
SK_ANALYSIS_JOB_META = "META#"
SK_CONVERSATION_TURN = "CONVERSATION_TURN#{timestamp}"
SK_LIFE_LOG = "LIFE_LOG#{date}#{seq}"
SK_DAILY_FUREMARU_SUMMARY = "DAILY_FUREMARU_SUMMARY#{date}"
SK_STRESS_SUMMARY = "STRESS_SUMMARY#{date}"
SK_EXPENSE = "EXPENSE#{timestamp}"
SK_REWARD_PERMIT = "REWARD_PERMIT#{timestamp}"
SK_REWARD_SKIP = "REWARD_SKIP#{timestamp}"
SK_MONTHLY_SUMMARY = "MONTHLY_SUMMARY#{yyyy_mm}"
SK_PUSH_SUBSCRIPTION = "PUSH_SUBSCRIPTION#"


class DataAccess:
    def __init__(self):
        config = get_config()
        self._dynamodb = boto3.resource("dynamodb", region_name=config["region"])
        self._table = self._dynamodb.Table(config["table_name"])

    # ─── Generic CRUD ───

    def put_item(self, pk: str, sk: str, data: dict) -> dict:
        item = {"PK": pk, "SK": sk, **data}
        self._table.put_item(Item=item)
        return item

    def get_item(self, pk: str, sk: str) -> dict | None:
        resp = self._table.get_item(Key={"PK": pk, "SK": sk})
        return resp.get("Item")

    def query_by_prefix(self, pk: str, sk_prefix: str, limit: int = 100) -> list:
        resp = self._table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
            Limit=limit,
        )
        return resp.get("Items", [])

    def query_between(self, pk: str, sk_start: str, sk_end: str) -> list:
        resp = self._table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").between(sk_start, sk_end),
        )
        return resp.get("Items", [])

    def update_item(self, pk: str, sk: str, updates: dict) -> None:
        expr_parts = []
        expr_values = {}
        expr_names = {}
        for i, (key, val) in enumerate(updates.items()):
            placeholder = f":v{i}"
            name_placeholder = f"#n{i}"
            expr_parts.append(f"{name_placeholder} = {placeholder}")
            expr_values[placeholder] = val
            expr_names[name_placeholder] = key

        self._table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )

    def delete_item(self, pk: str, sk: str) -> None:
        self._table.delete_item(Key={"PK": pk, "SK": sk})

    def batch_put(self, items: list[dict]) -> None:
        with self._table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)

    # ─── Identity Resolution ───

    def resolve_user_id(self, cognito_sub: str) -> str:
        """Resolve Cognito sub to internal user_id. Creates if not exists."""
        pk = f"IDENTITY#COGNITO#{cognito_sub}"
        sk = "META#"
        item = self.get_item(pk, sk)
        if item:
            return item["user_id"]

        # Create new user
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Write identity mapping
        self.put_item(pk, sk, {
            "user_id": user_id,
            "provider": "cognito",
            "created_at": now,
        })

        # Write initial profile
        self.put_item(f"USER#{user_id}", SK_PROFILE, {
            "display_name": "",
            "diary_time": "22:00",
            "notification_enabled": True,
            "monthly_surplus": 0,
            "created_at": now,
            "updated_at": now,
        })

        return user_id

    # ─── Profile Operations ───

    def get_or_create_profile(self, user_id: str) -> dict:
        """Get user profile, creating with defaults if missing."""
        item = self.get_item(f"USER#{user_id}", SK_PROFILE)
        if item:
            return item

        now = datetime.now(timezone.utc).isoformat()
        return self.put_item(f"USER#{user_id}", SK_PROFILE, {
            "display_name": "",
            "diary_time": "22:00",
            "notification_enabled": True,
            "monthly_surplus": 0,
            "created_at": now,
            "updated_at": now,
        })

    def update_profile(self, user_id: str, updates: dict) -> None:
        """Update user profile fields."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.update_item(f"USER#{user_id}", SK_PROFILE, updates)
