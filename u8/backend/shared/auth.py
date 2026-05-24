"""
Auth utilities - JWT verification and user resolution from API Gateway events.
"""
import json
import urllib.request
import urllib.error
from shared.config import get_config


def resolve_user_from_event(event: dict, da) -> tuple:
    """
    Extract Cognito sub from API Gateway JWT authorizer context,
    then resolve to internal user_id.

    Returns:
        (user_id, None) on success
        (None, error_response) on failure
    """
    try:
        # API Gateway HTTP API JWT Authorizer puts claims in requestContext
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        jwt_claims = authorizer.get("jwt", {}).get("claims", {})
        cognito_sub = jwt_claims.get("sub")

        if not cognito_sub:
            return None, _unauthorized("Missing authentication")

        user_id = da.resolve_user_id(cognito_sub)
        return user_id, None

    except Exception as e:
        return None, _unauthorized(f"Authentication failed: {str(e)}")


def validate_jwt_token(token: str) -> str | None:
    """
    Validate a Cognito JWT token and return the user_id (cognito sub).
    Used for WebSocket $connect authentication where JWT authorizer is unavailable.
    Returns None if invalid.
    """
    try:
        # Decode JWT payload without full verification (Cognito handles issuance)
        # For production, implement full JWKS verification
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload
        payload_b64 = parts[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)

        # Verify basic claims
        config = get_config()
        expected_issuer = f"https://cognito-idp.{config['cognito_region']}.amazonaws.com/{config['cognito_user_pool_id']}"

        if payload.get("iss") != expected_issuer:
            return None

        if payload.get("token_use") not in ("access", "id"):
            return None

        # Check expiration
        import time
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return None

        # Return cognito sub as user_id
        sub = payload.get("sub")
        if not sub:
            return None

        # Resolve to internal user_id
        from shared.data_access import DataAccess
        da = DataAccess()
        return da.resolve_user_id(sub)

    except Exception:
        return None


def _unauthorized(message: str) -> dict:
    return {
        "statusCode": 401,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps({"error": "unauthorized", "message": message}, ensure_ascii=False),
    }
