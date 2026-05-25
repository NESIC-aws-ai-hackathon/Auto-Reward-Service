"""
Voice Gateway Lambda - WebSocket API handler for Nova Sonic voice chat.
Routes: $connect, $disconnect, startSession, audioChunk, textMessage, endSession
"""
import json
import traceback
from decimal import Decimal
import boto3

from shared.config import get_config
from shared.data_access import DataAccess

config = get_config()
da = DataAccess()


def lambda_handler(event, context):
    """Main WebSocket route handler."""
    route_key = event.get("requestContext", {}).get("routeKey", "")
    connection_id = event.get("requestContext", {}).get("connectionId", "")
    print(f"[VoiceGW] route={route_key} conn={connection_id}")

    try:
        if route_key == "$connect":
            return handle_connect(event, connection_id)
        elif route_key == "$disconnect":
            return handle_disconnect(event, connection_id)
        elif route_key == "startSession":
            return handle_start_session(event, connection_id)
        elif route_key == "audioChunk":
            return handle_audio_chunk(event, connection_id)
        elif route_key == "textMessage":
            return handle_text_message(event, connection_id)
        elif route_key == "endSession":
            return handle_end_session(event, connection_id)
        else:
            return handle_default(event, connection_id)
    except Exception as e:
        traceback.print_exc()
        _send_to_client(connection_id, {
            "type": "error",
            "message": str(e),
        })
        return {"statusCode": 500}


def handle_connect(event, connection_id):
    """Authenticate user from query string token on WebSocket connect."""
    query_params = event.get("queryStringParameters") or {}
    token = query_params.get("token", "")

    if not token:
        return {"statusCode": 401, "body": "Missing token"}

    # Validate Cognito JWT
    from shared.auth import validate_jwt_token
    user_id = validate_jwt_token(token)
    if not user_id:
        return {"statusCode": 401, "body": "Invalid token"}

    # Store connection → user mapping in DynamoDB
    da.put_item(f"WS_CONNECTION#{connection_id}", "META#", {
        "connection_id": connection_id,
        "user_id": user_id,
        "status": "connected",
    })

    return {"statusCode": 200}


def handle_disconnect(event, connection_id):
    """Clean up on WebSocket disconnect."""
    # Get connection info
    conn = da.get_item(f"WS_CONNECTION#{connection_id}", "META#")
    if conn:
        # If there's an active session, abort it
        session_id = conn.get("active_session_id")
        if session_id:
            user_id = conn.get("user_id", "")
            _abort_session(user_id, session_id)

        # Delete connection record
        da._table.delete_item(Key={"PK": f"WS_CONNECTION#{connection_id}", "SK": "META#"})

    return {"statusCode": 200}


def handle_start_session(event, connection_id):
    """Start a new Nova Sonic voice session."""
    print(f"[VoiceGW] startSession conn={connection_id}")
    conn = da.get_item(f"WS_CONNECTION#{connection_id}", "META#")
    if not conn:
        print(f"[VoiceGW] startSession: no connection record found")
        return {"statusCode": 403}

    user_id = conn["user_id"]

    from services.sonic_voice_session import SonicVoiceSessionService
    svc = SonicVoiceSessionService(da)
    result = svc.start_session(user_id, connection_id)

    # Update connection with active session
    da.update_item(f"WS_CONNECTION#{connection_id}", "META#", {
        "active_session_id": result["session_id"],
    })

    _send_to_client(connection_id, {
        "type": "sessionStarted",
        "session_id": result["session_id"],
    })

    return {"statusCode": 200}


def handle_audio_chunk(event, connection_id):
    """Process audio chunk from client, invoke Nova Sonic, stream response back."""
    print(f"[VoiceGW] audioChunk conn={connection_id}")
    conn = da.get_item(f"WS_CONNECTION#{connection_id}", "META#")
    if not conn:
        return {"statusCode": 403}

    user_id = conn["user_id"]
    session_id = conn.get("active_session_id")
    if not session_id:
        _send_to_client(connection_id, {
            "type": "error",
            "message": "No active session. Call startSession first.",
        })
        return {"statusCode": 400}

    body = _parse_body(event)
    audio_data = body.get("audio", "")  # base64 encoded audio
    is_final = body.get("is_final", False)  # True when user finished speaking

    if not audio_data and not is_final:
        return {"statusCode": 200}

    from services.sonic_voice_session import SonicVoiceSessionService
    svc = SonicVoiceSessionService(da)

    # Process audio through Nova Sonic
    svc.process_audio_turn(
        user_id=user_id,
        session_id=session_id,
        connection_id=connection_id,
        audio_base64=audio_data,
        is_final=is_final,
    )

    return {"statusCode": 200}


def handle_text_message(event, connection_id):
    """Handle text-based message (fallback mode)."""
    conn = da.get_item(f"WS_CONNECTION#{connection_id}", "META#")
    if not conn:
        return {"statusCode": 403}

    user_id = conn["user_id"]
    session_id = conn.get("active_session_id")
    if not session_id:
        _send_to_client(connection_id, {
            "type": "error",
            "message": "No active session. Call startSession first.",
        })
        return {"statusCode": 400}

    body = _parse_body(event)
    text = body.get("text", "").strip()
    if not text:
        return {"statusCode": 200}

    from services.sonic_voice_session import SonicVoiceSessionService
    svc = SonicVoiceSessionService(da)

    svc.process_text_turn(
        user_id=user_id,
        session_id=session_id,
        connection_id=connection_id,
        text=text,
    )

    return {"statusCode": 200}


def handle_end_session(event, connection_id):
    """End the voice session."""
    conn = da.get_item(f"WS_CONNECTION#{connection_id}", "META#")
    if not conn:
        return {"statusCode": 403}

    user_id = conn["user_id"]
    session_id = conn.get("active_session_id")
    if not session_id:
        return {"statusCode": 200}

    from services.sonic_voice_session import SonicVoiceSessionService
    svc = SonicVoiceSessionService(da)
    result = svc.end_session(user_id, session_id)

    # Clear active session from connection
    da.update_item(f"WS_CONNECTION#{connection_id}", "META#", {
        "active_session_id": "",
    })

    _send_to_client(connection_id, {
        "type": "conversationEnded",
        "session_id": session_id,
        "analysis_job_id": result.get("analysis_job_id"),
        "duration_sec": result.get("duration_sec", 0),
        "turn_count": result.get("turn_count", 0),
    })

    return {"statusCode": 200}


def handle_default(event, connection_id):
    """Handle unknown routes."""
    _send_to_client(connection_id, {
        "type": "error",
        "message": "Unknown action",
    })
    return {"statusCode": 200}


def _abort_session(user_id: str, session_id: str):
    """Abort a session on unexpected disconnect."""
    from services.sonic_voice_session import SonicVoiceSessionService
    try:
        svc = SonicVoiceSessionService(da)
        svc.abort_session(user_id, session_id)
    except Exception:
        pass


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _send_to_client(connection_id: str, data: dict):
    """Send message back to WebSocket client via API Gateway Management API."""
    endpoint = config.get("websocket_api_endpoint", "")
    if not endpoint:
        print(f"[VoiceGW] _send_to_client: no endpoint configured")
        return

    client = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data, ensure_ascii=False, cls=_DecimalEncoder).encode("utf-8"),
        )
    except client.exceptions.GoneException:
        # Connection no longer exists
        print(f"[VoiceGW] _send_to_client: connection gone")
    except Exception as e:
        print(f"[VoiceGW] _send_to_client error: {e}")


def _parse_body(event) -> dict:
    """Parse WebSocket message body."""
    body = event.get("body", "")
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {}
