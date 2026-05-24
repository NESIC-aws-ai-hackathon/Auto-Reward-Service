"""
Configuration module - reads environment variables.
"""
import os


def get_config() -> dict:
    return {
        "table_name": os.environ.get("TABLE_NAME", "ArsTable"),
        "region": os.environ.get("AWS_REGION", "ap-northeast-1"),
        "env": os.environ.get("ENV", "dev"),
        "cognito_user_pool_id": os.environ.get("COGNITO_USER_POOL_ID", ""),
        "cognito_client_id": os.environ.get("COGNITO_CLIENT_ID", ""),
        "cognito_region": os.environ.get("COGNITO_REGION", "ap-northeast-1"),
        "analysis_queue_url": os.environ.get("ANALYSIS_QUEUE_URL", ""),
        "bedrock_region": os.environ.get("BEDROCK_REGION", "us-east-1"),
        "bedrock_model_id": os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        "nova_sonic_model_id": os.environ.get("NOVA_SONIC_MODEL_ID", "amazon.nova-sonic-v1:0"),
        "websocket_api_endpoint": os.environ.get("WEBSOCKET_API_ENDPOINT", ""),
        "vapid_private_key": os.environ.get("VAPID_PRIVATE_KEY", ""),
        "vapid_public_key": os.environ.get("VAPID_PUBLIC_KEY", ""),
        "vapid_subject": os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com"),
    }
