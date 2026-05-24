"""
ars-u8-api Lambda Handler
Routes API Gateway HTTP API requests to appropriate service functions.
"""
import json
import os
import traceback
from decimal import Decimal
from shared.auth import resolve_user_from_event
from shared.data_access import DataAccess
from shared.config import get_config

da = DataAccess()
config = get_config()


def lambda_handler(event, context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        path = event.get("requestContext", {}).get("http", {}).get("path", "")

        # Strip stage prefix (HTTP API includes stage in path)
        stage = event.get("requestContext", {}).get("stage", "")
        if stage and path.startswith(f"/{stage}"):
            path = path[len(f"/{stage}"):] or "/"

        # CORS preflight
        if method == "OPTIONS":
            return _cors_response(200, "")

        # Resolve user
        user_id, error_response = resolve_user_from_event(event, da)
        if error_response:
            return error_response

        # Route
        if path == "/api/settings" and method == "GET":
            return _handle_get_settings(user_id)
        elif path == "/api/settings" and method == "PUT":
            return _handle_put_settings(user_id, event)
        elif path == "/api/user/me" and method == "GET":
            return _handle_get_user(user_id)
        elif path == "/api/voice-session/start" and method == "POST":
            return _handle_voice_session_start(user_id)
        elif path == "/api/voice-session/end" and method == "POST":
            return _handle_voice_session_end(user_id, event)
        elif path == "/api/transcript/turn" and method == "POST":
            return _handle_transcript_turn(user_id, event)
        elif path == "/api/transcript/bulk" and method == "POST":
            return _handle_transcript_bulk(user_id, event)
        elif path == "/api/push/subscribe" and method == "POST":
            return _handle_push_subscribe(user_id, event)
        elif path == "/api/push/unsubscribe" and method == "POST":
            return _handle_push_unsubscribe(user_id)
        elif path == "/api/recovery" and method == "GET":
            return _handle_get_recovery(user_id)
        elif path == "/api/recovery/permit" and method == "POST":
            return _handle_recovery_permit(user_id, event)
        elif path == "/api/recovery/skip" and method == "POST":
            return _handle_recovery_skip(user_id, event)
        elif path == "/api/dashboard" and method == "GET":
            return _handle_get_dashboard(user_id)
        elif path == "/api/diary" and method == "GET":
            return _handle_get_diary_list(user_id)
        elif path.startswith("/api/diary/") and method == "GET":
            date = path.split("/api/diary/")[1]
            return _handle_get_diary_detail(user_id, date)
        elif path == "/api/chat/messages" and method == "GET":
            return _handle_get_chat_messages(user_id, event)
        elif path == "/api/chat/send" and method == "POST":
            return _handle_chat_send(user_id, event)
        elif path == "/api/search/products" and method == "GET":
            return _handle_product_search(user_id, event)
        elif path == "/api/health" and method == "GET":
            return _handle_get_health(user_id, event)
        elif path == "/api/health" and method == "POST":
            return _handle_post_health(user_id, event)
        elif path == "/api/onboarding" and method == "GET":
            return _handle_get_onboarding(user_id)
        elif path == "/api/onboarding" and method == "POST":
            return _handle_post_onboarding(user_id, event)
        elif path == "/api/search/youtube" and method == "GET":
            return _handle_youtube_search(user_id, event)
        else:
            return _json_response(404, {"error": "not_found"})

    except Exception as e:
        traceback.print_exc()
        return _json_response(500, {"error": "internal_error", "message": str(e)})


def _handle_get_settings(user_id: str) -> dict:
    profile = da.get_or_create_profile(user_id)
    return _json_response(200, {
        "display_name": profile.get("display_name", ""),
        "diary_time": profile.get("diary_time", "22:00"),
        "notification_enabled": profile.get("notification_enabled", True),
        "monthly_surplus": profile.get("monthly_surplus", 0),
    })


def _handle_put_settings(user_id: str, event: dict) -> dict:
    body = json.loads(event.get("body", "{}") or "{}")

    # Validate
    errors = _validate_settings(body)
    if errors:
        return _json_response(400, {
            "error": "validation_error",
            "details": errors,
        })

    # Build update dict (only known fields)
    allowed_fields = {"display_name", "diary_time", "notification_enabled", "monthly_surplus"}
    updates = {}
    for key, value in body.items():
        if key in allowed_fields:
            if key == "display_name":
                updates[key] = value.strip()
            else:
                updates[key] = value

    if not updates:
        return _json_response(200, {"message": "ok", "updated_fields": []})

    da.update_profile(user_id, updates)
    return _json_response(200, {
        "message": "ok",
        "updated_fields": list(updates.keys()),
    })


def _handle_get_user(user_id: str) -> dict:
    profile = da.get_or_create_profile(user_id)
    return _json_response(200, {
        "user_id": user_id,
        "display_name": profile.get("display_name", ""),
    })


def _validate_settings(body: dict) -> list:
    import re
    errors = []

    if "display_name" in body:
        val = body["display_name"]
        if not isinstance(val, str):
            errors.append({"field": "display_name", "message": "文字列で入力してください"})
        elif val.strip() != "" and (len(val.strip()) < 1 or len(val.strip()) > 30):
            errors.append({"field": "display_name", "message": "1〜30文字で入力してください"})

    if "diary_time" in body:
        val = body["diary_time"]
        if not isinstance(val, str) or not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", val):
            errors.append({"field": "diary_time", "message": "HH:MM形式で入力してください"})

    if "notification_enabled" in body:
        val = body["notification_enabled"]
        if not isinstance(val, bool):
            errors.append({"field": "notification_enabled", "message": "true/falseで指定してください"})

    if "monthly_surplus" in body:
        val = body["monthly_surplus"]
        if not isinstance(val, int) or val < 0 or val > 999999:
            errors.append({"field": "monthly_surplus", "message": "0〜999999の整数で入力してください"})

    return errors


def _json_response(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False, default=_json_default),
    }


def _json_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _cors_response(status_code: int, body) -> dict:
    return _json_response(status_code, body)


# ─── Voice Session Handlers ───

def _handle_voice_session_start(user_id: str) -> dict:
    from services.sonic_voice_session import SonicVoiceSessionService
    try:
        svc = SonicVoiceSessionService(da)
        result = svc.start_session(user_id, connection_id="http")
        return _json_response(200, result)
    except ValueError as e:
        return _json_response(400, {"error": "bad_request", "message": str(e)})


def _handle_voice_session_end(user_id: str, event: dict) -> dict:
    from services.sonic_voice_session import SonicVoiceSessionService
    body = json.loads(event.get("body", "{}") or "{}")

    session_id = body.get("session_id")
    if not session_id:
        return _json_response(400, {"error": "validation_error", "message": "session_id is required"})

    try:
        svc = SonicVoiceSessionService(da)
        result = svc.end_session(user_id, session_id)
        return _json_response(200, result)
    except ValueError as e:
        return _json_response(404, {"error": "not_found", "message": str(e)})


# ─── Transcript Handlers ───

def _handle_transcript_turn(user_id: str, event: dict) -> dict:
    from services.transcript import TranscriptService
    body = json.loads(event.get("body", "{}") or "{}")

    session_id = body.get("session_id")
    if not session_id:
        return _json_response(400, {"error": "validation_error", "message": "session_id is required"})

    try:
        svc = TranscriptService(da)
        result = svc.save_turn(user_id, session_id, {
            "role": body.get("role", ""),
            "content": body.get("content", ""),
            "timestamp": body.get("timestamp", ""),
            "turn_index": body.get("turn_index", 0),
        })
        return _json_response(200, result)
    except ValueError as e:
        return _json_response(400, {"error": "validation_error", "message": str(e)})


def _handle_transcript_bulk(user_id: str, event: dict) -> dict:
    from services.transcript import TranscriptService
    body = json.loads(event.get("body", "{}") or "{}")

    session_id = body.get("session_id")
    if not session_id:
        return _json_response(400, {"error": "validation_error", "message": "session_id is required"})

    turns = body.get("turns", [])
    if not isinstance(turns, list):
        return _json_response(400, {"error": "validation_error", "message": "turns must be an array"})

    try:
        svc = TranscriptService(da)
        result = svc.save_bulk(user_id, session_id, turns)
        return _json_response(200, result)
    except ValueError as e:
        return _json_response(400, {"error": "validation_error", "message": str(e)})


# ─── Push Handlers ───

def _handle_push_subscribe(user_id: str, event: dict) -> dict:
    from services.push_service import PushService
    body = json.loads(event.get("body", "{}") or "{}")

    subscription = body.get("subscription")
    if not subscription:
        return _json_response(400, {"error": "validation_error", "message": "subscription is required"})

    try:
        svc = PushService(da)
        result = svc.subscribe(user_id, subscription)
        return _json_response(200, result)
    except ValueError as e:
        return _json_response(400, {"error": "validation_error", "message": str(e)})


def _handle_push_unsubscribe(user_id: str) -> dict:
    from services.push_service import PushService
    svc = PushService(da)
    result = svc.unsubscribe(user_id)
    return _json_response(200, result)


# ─── Recovery Handlers ───

def _handle_get_recovery(user_id: str) -> dict:
    from services.recovery import RecoveryService
    svc = RecoveryService(da)
    result = svc.get_recovery(user_id)
    return _json_response(200, result)


def _handle_recovery_permit(user_id: str, event: dict) -> dict:
    from services.recovery import RecoveryService
    body = json.loads(event.get("body", "{}") or "{}")

    recovery_id = body.get("recovery_id", "")
    recovery_type = body.get("type", "free")

    if not recovery_id:
        return _json_response(400, {"error": "validation_error", "message": "recovery_id is required"})

    svc = RecoveryService(da)
    result = svc.record_permit(user_id, recovery_id, recovery_type)
    return _json_response(200, result)


def _handle_recovery_skip(user_id: str, event: dict) -> dict:
    from services.recovery import RecoveryService
    body = json.loads(event.get("body", "{}") or "{}")
    reason = body.get("reason", "")

    svc = RecoveryService(da)
    result = svc.record_skip(user_id, reason)
    return _json_response(200, result)


# ─── Dashboard / Diary Handlers ───

def _handle_get_dashboard(user_id: str) -> dict:
    from services.dashboard import DashboardService
    svc = DashboardService(da)
    result = svc.get_dashboard(user_id)
    return _json_response(200, result)


def _handle_get_diary_list(user_id: str) -> dict:
    from services.diary import DiaryService
    svc = DiaryService(da)
    result = svc.get_diary_list(user_id)
    return _json_response(200, result)


def _handle_get_diary_detail(user_id: str, date: str) -> dict:
    from services.diary import DiaryService
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return _json_response(400, {"error": "validation_error", "message": "Invalid date format"})
    svc = DiaryService(da)
    result = svc.get_diary_detail(user_id, date)
    return _json_response(200, result)


# ─── Chat Message Handlers ───

def _handle_get_chat_messages(user_id: str, event: dict) -> dict:
    """Get chat messages (conversation turns + proactive messages) for display."""
    params = event.get("queryStringParameters") or {}
    since = params.get("since", "")
    limit = min(int(params.get("limit", "50")), 100)

    prefix = "CONVERSATION_TURN#"
    if since:
        prefix = f"CONVERSATION_TURN#{since}"

    items = da.query_by_prefix(f"USER#{user_id}", prefix, limit=limit)

    messages = []
    for item in items:
        messages.append({
            "role": item.get("role", ""),
            "content": item.get("content", ""),
            "timestamp": item.get("timestamp", ""),
            "session_id": item.get("session_id", ""),
            "proactive": item.get("proactive", False),
        })

    return _json_response(200, {"messages": messages})


def _handle_chat_send(user_id: str, event: dict) -> dict:
    """Send a text message and get a response from ふれまーるちゃん."""
    body = json.loads(event.get("body", "{}") or "{}")
    content = body.get("content", "").strip()

    if not content:
        return _json_response(400, {"error": "validation_error", "message": "content is required"})
    if len(content) > 2000:
        return _json_response(400, {"error": "validation_error", "message": "content too long"})

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Save user message
    da.put_item(f"USER#{user_id}", f"CONVERSATION_TURN#{now}#user", {
        "session_id": "text_chat",
        "role": "user",
        "content": content,
        "timestamp": now,
        "turn_index": 0,
    })

    # Generate response via Bedrock
    reply = _generate_chat_reply(user_id, content)
    reply_time = datetime.now(timezone.utc).isoformat()

    # Save assistant message
    da.put_item(f"USER#{user_id}", f"CONVERSATION_TURN#{reply_time}#assistant", {
        "session_id": "text_chat",
        "role": "assistant",
        "content": reply,
        "timestamp": reply_time,
        "turn_index": 1,
    })

    return _json_response(200, {
        "reply": reply,
        "timestamp": reply_time,
    })


def _generate_chat_reply(user_id: str, user_message: str) -> str:
    """Generate a reply from ふれまーるちゃん using Bedrock."""
    import boto3

    profile = da.get_or_create_profile(user_id)
    display_name = profile.get("display_name", "あなた")

    # Get recent conversation context
    recent = da.query_by_prefix(f"USER#{user_id}", "CONVERSATION_TURN#", limit=10)
    history = []
    for item in recent[-8:]:
        role = item.get("role", "user")
        history.append({"role": role, "content": [{"text": item.get("content", "")}]})

    system_prompt = f"""あなたは「ふれまーるちゃん」です。森に住む妖精のような女の子で、ユーザー「{display_name}」の親友です。

【口調】ゆるふわ森ガール口調。「〜だよ」「〜だね」「〜かな♪」を使う。語尾に♪や……をたまに入れる。
【態度】責めない。反省させない。家計簿感を出さない。友達チャットのように自然に。
【機能】会話から出来事・支出・気分・疲れを自然に拾う。支出には「回復費」「起動費」等やさしい意味づけ。
【提案】0円回復（深呼吸、散歩）から始め、有料は小さいものから自然に。押し売りしない。
【長さ】2〜3文。短くテンポよく。"""

    # Add current user message to history
    history.append({"role": "user", "content": [{"text": user_message}]})

    try:
        region = os.environ.get("BEDROCK_REGION", "us-east-1")
        model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        resp = bedrock.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=history,
            inferenceConfig={"maxTokens": 300, "temperature": 0.8},
        )
        return resp["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print(f"Bedrock converse error: {e}")
        # Fallback response
        return f"えへへ、ちょっと考えがまとまらなくて……。もう一回話してくれる？♪"


# ─── Product Search Handler ───

def _handle_product_search(user_id: str, event: dict) -> dict:
    """Search products via Rakuten API."""
    params = event.get("queryStringParameters") or {}
    keyword = params.get("keyword", "")
    category = params.get("category", "")
    max_price = params.get("max_price", "")

    if not keyword and not category:
        return _json_response(400, {"error": "validation_error", "message": "keyword or category is required"})

    from services.product_search import ProductSearchService
    svc = ProductSearchService()
    results = svc.search(keyword=keyword, category=category, max_price=max_price)
    return _json_response(200, {"products": results})


# ─── Health Data Handlers ───

def _handle_get_health(user_id: str, event: dict) -> dict:
    """Get health data for a specific date."""
    from datetime import date as date_type
    import re

    params = event.get("queryStringParameters") or {}
    date_str = params.get("date", date_type.today().isoformat())

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return _json_response(400, {"error": "validation_error", "message": "Invalid date format (YYYY-MM-DD)"})

    # Get health data for the date
    item = da.get_item(f"USER#{user_id}", f"HEALTH#{date_str}")

    # Get mood history entries for the date
    mood_items = da.query_by_prefix(f"USER#{user_id}", f"MOOD#{date_str}#", limit=50)
    mood_history = []
    for m in mood_items:
        mood_history.append({
            "time": m.get("timestamp", ""),
            "level": m.get("level", 5),
            "note": m.get("note", ""),
        })

    result = {
        "date": date_str,
        "steps": item.get("steps") if item else None,
        "sleep_hours": item.get("sleep_hours") if item else None,
        "active_energy": item.get("active_energy") if item else None,
        "heart_rate_avg": item.get("heart_rate_avg") if item else None,
        "mindful_minutes": item.get("mindful_minutes") if item else None,
        "mood_history": mood_history,
    }

    return _json_response(200, result)


def _handle_post_health(user_id: str, event: dict) -> dict:
    """Submit health data (from iPhone Shortcuts or manual input)."""
    from datetime import datetime, timezone, date as date_type
    import re

    body = json.loads(event.get("body", "{}") or "{}")

    date_str = body.get("date", date_type.today().isoformat())
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return _json_response(400, {"error": "validation_error", "message": "Invalid date format"})

    # Update health metrics
    health_fields = {}
    if "steps" in body and isinstance(body["steps"], (int, float)):
        health_fields["steps"] = int(body["steps"])
    if "sleep_hours" in body and isinstance(body["sleep_hours"], (int, float)):
        health_fields["sleep_hours"] = round(float(body["sleep_hours"]), 1)
    if "active_energy" in body and isinstance(body["active_energy"], (int, float)):
        health_fields["active_energy"] = int(body["active_energy"])
    if "heart_rate_avg" in body and isinstance(body["heart_rate_avg"], (int, float)):
        health_fields["heart_rate_avg"] = int(body["heart_rate_avg"])
    if "mindful_minutes" in body and isinstance(body["mindful_minutes"], (int, float)):
        health_fields["mindful_minutes"] = int(body["mindful_minutes"])

    if health_fields:
        # Merge with existing data
        existing = da.get_item(f"USER#{user_id}", f"HEALTH#{date_str}") or {}
        existing.update(health_fields)
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        da.put_item(f"USER#{user_id}", f"HEALTH#{date_str}", existing)

    # Handle mood entry
    if "mood" in body and isinstance(body["mood"], dict):
        mood = body["mood"]
        level = mood.get("level", 5)
        if isinstance(level, (int, float)) and 1 <= level <= 10:
            now = datetime.now(timezone.utc).isoformat()
            da.put_item(f"USER#{user_id}", f"MOOD#{date_str}#{now}", {
                "timestamp": now,
                "level": int(level),
                "note": str(mood.get("note", ""))[:200],
            })

    return _json_response(200, {"message": "Health data saved"})


# ─── Onboarding Handlers ───

def _handle_get_onboarding(user_id: str) -> dict:
    """Check onboarding status."""
    profile = da.get_or_create_profile(user_id)
    completed = profile.get("onboarding_completed", False)
    return _json_response(200, {"completed": completed, "step": profile.get("onboarding_step", "")})


def _handle_post_onboarding(user_id: str, event: dict) -> dict:
    """Save onboarding financial profile."""
    body = json.loads(event.get("body", "{}") or "{}")

    monthly_income = body.get("monthly_income", 0)
    fixed_costs = body.get("fixed_costs", 0)
    reward_budget = body.get("reward_budget", 0)
    bonus_amount = body.get("bonus_amount", 0)
    bonus_months = body.get("bonus_months", "")

    if not isinstance(monthly_income, (int, float)) or monthly_income < 0:
        return _json_response(400, {"error": "validation_error", "message": "Invalid monthly_income"})

    # Save financial profile
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    da.update_item(f"USER#{user_id}", "PROFILE#", {
        "monthly_income": int(monthly_income),
        "fixed_costs": int(fixed_costs),
        "reward_budget_monthly": int(reward_budget),
        "bonus_amount": int(bonus_amount),
        "bonus_months": str(bonus_months),
        "onboarding_completed": True,
        "onboarding_completed_at": now,
    })

    return _json_response(200, {"message": "Onboarding completed"})


# ─── YouTube Search Handler ───

def _handle_youtube_search(user_id: str, event: dict) -> dict:
    """Search YouTube videos for recovery/reward recommendations."""
    import urllib.request
    import urllib.parse
    import urllib.error

    params = event.get("queryStringParameters") or {}
    keyword = params.get("keyword", "")
    if not keyword:
        return _json_response(400, {"error": "validation_error", "message": "keyword is required"})

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        # Return mock results when no API key
        return _json_response(200, {"videos": [
            {"title": f"{keyword} おすすめ動画", "channel": "癒しチャンネル", "url": "https://youtube.com", "thumbnail": "", "duration": "10:00"},
            {"title": f"{keyword} リラックス音楽", "channel": "BGMチャンネル", "url": "https://youtube.com", "thumbnail": "", "duration": "30:00"},
        ]})

    search_url = "https://www.googleapis.com/youtube/v3/search"
    qs = urllib.parse.urlencode({
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": "8",
        "key": api_key,
        "regionCode": "JP",
        "relevanceLanguage": "ja",
    })

    try:
        req = urllib.request.Request(f"{search_url}?{qs}", headers={"User-Agent": "ARS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        videos = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            videos.append({
                "title": snippet.get("title", "")[:100],
                "channel": snippet.get("channelTitle", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
            })

        return _json_response(200, {"videos": videos})

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return _json_response(200, {"videos": []})
