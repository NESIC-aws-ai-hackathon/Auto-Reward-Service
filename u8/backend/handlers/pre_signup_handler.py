"""
Pre Sign-up Lambda Trigger for Cognito.
Limits user registration to a maximum of 7 users.
"""
import boto3
import os


def lambda_handler(event, context):
    """Check user count before allowing sign-up."""
    user_pool_id = event.get("userPoolId", "")
    max_users = int(os.environ.get("MAX_USERS", "7"))

    client = boto3.client("cognito-idp")

    # Count existing users
    user_count = 0
    pagination_token = None

    while True:
        params = {
            "UserPoolId": user_pool_id,
            "Limit": 60,
        }
        if pagination_token:
            params["PaginationToken"] = pagination_token

        resp = client.list_users(**params)
        user_count += len(resp.get("Users", []))

        if user_count >= max_users:
            raise Exception(f"ごめんね、今は新規登録を受け付けていないの……（上限{max_users}人）")

        pagination_token = resp.get("PaginationToken")
        if not pagination_token:
            break

    # Allow sign-up
    return event
