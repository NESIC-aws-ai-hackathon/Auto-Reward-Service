"""
ars-u8-analysis Lambda Handler
Processes conversation analysis jobs (SQS) and scheduled diary generation (EventBridge).
"""
import json
import traceback
from datetime import datetime, timezone, timedelta

from shared.data_access import DataAccess
from shared.config import get_config
from services.analysis import AnalysisService
from services.push_service import PushService

da = DataAccess()
config = get_config()


def lambda_handler(event, context):
    """Handle SQS messages and EventBridge scheduled events."""
    # EventBridge trigger
    if event.get("source") == "aws.events" or event.get("trigger"):
        trigger = event.get("trigger") or event.get("detail-type", "")
        if "diary" in trigger.lower() or "scheduled" in trigger.lower():
            return handle_scheduled_diary()
        elif "reprocess" in trigger.lower():
            return handle_reprocess()
        elif "proactive" in trigger.lower():
            return handle_proactive_messages()
        return handle_scheduled_diary()

    # SQS trigger
    records = event.get("Records", [])
    results = []
    for record in records:
        try:
            body = json.loads(record.get("body", "{}"))
            job_type = body.get("job_type", "")

            if job_type == "conversation_analysis":
                process_conversation_job(body)
                results.append({"job_id": body.get("job_id"), "status": "success"})
            elif job_type == "daily_diary":
                process_diary_job(body)
                results.append({"user_id": body.get("user_id"), "status": "success"})
            else:
                results.append({"error": f"unknown job_type: {job_type}"})

        except Exception as e:
            traceback.print_exc()
            results.append({"error": str(e)})

    return {"processed": len(results), "results": results}


def process_conversation_job(body: dict) -> None:
    """Process a conversation analysis job."""
    job_id = body["job_id"]
    user_id = body["user_id"]
    session_id = body["session_id"]

    svc = AnalysisService(da)
    svc.process_conversation(job_id, user_id, session_id)

    # Stress assessment (U8-D)
    stress_result = svc.assess_stress(user_id, session_id)

    # Send push if stress is high
    if stress_result.get("stress_level", 0) >= 3:
        push = PushService(da)
        profile = da.get_or_create_profile(user_id)
        if profile.get("notification_enabled", True):
            push.send_notification(
                user_id,
                "💆 ちょっと休憩しない？",
                "今日は少しお疲れみたい。回復案を用意したよ♪",
            )


def process_diary_job(body: dict) -> None:
    """Process a diary generation job for a single user."""
    user_id = body["user_id"]
    date = body.get("date")

    svc = AnalysisService(da)
    diary_text = svc.generate_diary_summary(user_id, date)

    # Send push notification
    if diary_text:
        push = PushService(da)
        profile = da.get_or_create_profile(user_id)
        if profile.get("notification_enabled", True):
            push.send_notification(
                user_id,
                "📖 今日の日記ができたよ",
                diary_text[:100] + ("..." if len(diary_text) > 100 else ""),
            )


def handle_scheduled_diary() -> dict:
    """Generate diary summaries for all active users (triggered by EventBridge at 22:00 JST)."""
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y-%m-%d")

    # Scan for users with today's life logs
    # Note: In production, this would use a GSI or user registry
    # For MVP, we query known users from recent analysis jobs
    recent_jobs = _get_recent_completed_jobs(today)
    processed_users = set()
    results = []

    for job in recent_jobs:
        user_id = job.get("user_id")
        if not user_id or user_id in processed_users:
            continue
        processed_users.add(user_id)

        try:
            svc = AnalysisService(da)
            diary_text = svc.generate_diary_summary(user_id, today)

            # Send push
            push = PushService(da)
            profile = da.get_or_create_profile(user_id)
            if profile.get("notification_enabled", True):
                push.send_notification(
                    user_id,
                    "📖 今日の日記ができたよ",
                    diary_text[:100] + ("..." if len(diary_text) > 100 else ""),
                )
            results.append({"user_id": user_id, "status": "success"})
        except Exception as e:
            results.append({"user_id": user_id, "status": "error", "error": str(e)})

    return {"processed_users": len(processed_users), "results": results}


def handle_reprocess() -> dict:
    """Reprocess failed/stuck analysis jobs."""
    # Query for jobs that are still queued after 10 minutes
    # This is a safety net for SQS delivery failures
    return {"reprocessed": 0}


def _get_recent_completed_jobs(date: str) -> list:
    """Get completed analysis jobs for today to find active users."""
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=config["region"])
    table = dynamodb.Table(config["table_name"])

    try:
        resp = table.scan(
            FilterExpression="begins_with(PK, :pk) AND #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":pk": "ANALYSIS_JOB#",
                ":status": "completed",
            },
            Limit=100,
        )
        return resp.get("Items", [])
    except Exception:
        return []


def handle_proactive_messages() -> dict:
    """Handle scheduled proactive message generation (10:00-21:00 JST)."""
    try:
        from services.proactive_message import ProactiveMessageService
        svc = ProactiveMessageService(da)
        result = svc.run_scheduled()
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        traceback.print_exc()
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
