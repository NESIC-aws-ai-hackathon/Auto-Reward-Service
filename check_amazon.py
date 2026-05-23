"""Check CloudWatch logs for Amazon cart operations"""
import boto3
import time
from datetime import datetime, timedelta, timezone

session = boto3.Session(profile_name='share', region_name='ap-northeast-1')
logs = session.client('logs')

log_group = '/aws/lambda/LiffApiFunction'
now = int(time.time() * 1000)
start = now - 3600_000  # last 1 hour

# 1. All recent log events (not just REPORT)
print("=== Recent LiffApiFunction logs (last 1h) ===")
try:
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start,
        endTime=now,
        filterPattern='?amazon ?cart ?add-to-cart ?purchase ?confirm',
        limit=50
    )
    events = resp.get('events', [])
    if not events:
        print("No amazon/cart related logs found")
    for ev in events:
        ts = datetime.fromtimestamp(ev['timestamp']/1000, tz=timezone(timedelta(hours=9)))
        print(f"[{ts.strftime('%H:%M:%S')}] {ev['message'].strip()[:300]}")
except Exception as e:
    print(f"Error: {e}")

# 2. Check for ANY errors
print("\n\n=== Errors (last 1h) ===")
try:
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start,
        endTime=now,
        filterPattern='?ERROR ?Traceback ?Exception ?error',
        limit=30
    )
    events = resp.get('events', [])
    if not events:
        print("No errors found")
    for ev in events:
        ts = datetime.fromtimestamp(ev['timestamp']/1000, tz=timezone(timedelta(hours=9)))
        print(f"[{ts.strftime('%H:%M:%S')}] {ev['message'].strip()[:300]}")
except Exception as e:
    print(f"Error: {e}")

# 3. Check ALL recent logs (last 15 min, no filter)
print("\n\n=== ALL logs (last 15 min) ===")
try:
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=now - 900_000,
        endTime=now,
        limit=80
    )
    events = resp.get('events', [])
    if not events:
        print("No logs in last 15 min")
    for ev in events:
        ts = datetime.fromtimestamp(ev['timestamp']/1000, tz=timezone(timedelta(hours=9)))
        msg = ev['message'].strip()
        if msg.startswith('START') or msg.startswith('END'):
            continue
        print(f"[{ts.strftime('%H:%M:%S')}] {msg[:250]}")
except Exception as e:
    print(f"Error: {e}")
