from __future__ import annotations

import base64
import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.line_service import get_line_service
from services.dynamodb_service import DynamoDBService
from utils.exceptions import LineServiceError
from utils.logger import get_logger

from handlers.intent_classifier import classify_intent
from handlers.character_reply import generate_reply
from handlers.onboarding_flow import (
    handle_onboarding,
    STEP_COMPLETED,
)
import handlers.expense_extractor as expense_extractor
import handlers.receipt_analyzer as receipt_analyzer
import handlers.reward_proposal as reward_proposal_handler
from handlers.character_reply import _infer_emotion
from models.schemas import SK_PENDING_CLARIFICATION, SK_PENDING_EXPENSE

logger = get_logger(__name__)

DAILY_CHAT_LIMIT = int(os.getenv("DAILY_CHAT_LIMIT", "50"))
MAX_INPUT_LENGTH = 1000

DAILY_LIMIT_REPLY = (
    "今日はもうたくさん話したね！リワードちゃん、ちょっと休憩するよ🥱\n"
    "また明日話しかけてね✨"
)
INPUT_TOO_LONG_REPLY = (
    "ちょっと長すぎて読み切れなかったよ😅\n"
    "1000文字以内でもう一度話しかけてね！"
)

UNSUPPORTED_REPLIES = [
    "スタンプかわいい！でもリワードちゃん、文字の方が得意なんだ😊",
    "んそれはまだ読めないかも！テキストで話しかけてくれると嬉しいな",
    "おっ、それ気になる！けど今はテキストだけ対応してるんだ～🥲",
]

ERROR_REPLY = "ちょっと調子が悪いみたい…またあとで話しかけてね🥲"

_ddb = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event, context):
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    signature = _get_signature(event)
    if not signature or not get_line_service().verify_signature(body, signature):
        logger.warning("signature_verification_failed")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        payload = json.loads(body)
        events = payload.get("events", [])
        for line_event in events:
            try:
                _route_event(line_event)
            except Exception as e:
                _handle_error(line_event, e)
    except json.JSONDecodeError:
        logger.exception("webhook_body_parse_error")

    return {"statusCode": 200, "body": "OK"}


def _get_signature(event):
    headers = event.get("headers") or {}
    return headers.get("x-line-signature") or headers.get("X-Line-Signature")


def _route_event(event):
    event_type = event.get("type")
    if event_type == "message":
        _route_message(event)
    elif event_type == "follow":
        _handle_follow(event)
    else:
        logger.info("unhandled_event_type", event_type=event_type)


def _handle_follow(event):
    user_id = (event.get("source") or {}).get("userId", "")
    reply_token = event.get("replyToken", "")
    if not user_id:
        return

    ddb = _get_ddb()
    pk = f"USER#{user_id}"
    existing = ddb.get_item(pk=pk, sk="PROFILE#")
    if not existing:
        now = datetime.now(timezone.utc).isoformat()
        ddb.put_item(pk, "PROFILE#", {
            "entityType": "PROFILE",
            "status": "ONBOARDING",
            "tone": "friendly",
            "push_count_this_month": 0,
            "line_user_id": user_id,
            "createdAt": now,
            "updatedAt": now,
        })

    welcome_text = handle_onboarding(user_id, None, ddb)
    get_line_service().reply_message(
        reply_token, [{"type": "text", "text": welcome_text}]
    )


def _route_message(event):
    message = event.get("message") or {}
    message_type = message.get("type")
    reply_token = event.get("replyToken", "")
    user_id = (event.get("source") or {}).get("userId", "")

    # 初回メッセージフォールバック: PROFILE# がなければオンボーディング直行
    if user_id:
        ddb = _get_ddb()
        pk = f"USER#{user_id}"
        if not ddb.get_item(pk=pk, sk="PROFILE#"):
            now = datetime.now(timezone.utc).isoformat()
            ddb.put_item(pk, "PROFILE#", {
                "entityType": "PROFILE",
                "status": "ONBOARDING",
                "tone": "friendly",
                "push_count_this_month": 0,
                "line_user_id": user_id,
                "createdAt": now,
                "updatedAt": now,
            })
            reply_text = handle_onboarding(user_id, None, ddb)
            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            return

    if message_type == "text":
        text = message.get("text", "")
        _handle_text(user_id, text, reply_token)
    elif message_type == "image":
        message_id = message.get("id", "")
        _handle_image(user_id, message_id, reply_token)
    else:
        reply_text = random.choice(UNSUPPORTED_REPLIES)
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )


def _handle_text(user_id, text, reply_token):
    ddb = _get_ddb()

    if len(text) > MAX_INPUT_LENGTH:
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": INPUT_TOO_LONG_REPLY}]
        )
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_sk = f"DAILY_COUNT#{today}"
    pk = f"USER#{user_id}"

    count_item = ddb.get_item(pk=pk, sk=daily_sk)
    current_count = int((count_item or {}).get("count", 0))
    if current_count >= DAILY_CHAT_LIMIT:
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": DAILY_LIMIT_REPLY}]
        )
        return

    # ONBOARDING_STATE 継続チェック: 途中離脱から戻った場合も Intent 分類をスキップして直行
    onboarding_state_check = ddb.get_item(pk=pk, sk="ONBOARDING_STATE#") or {}
    if onboarding_state_check.get("step", "") not in ("", STEP_COMPLETED):
        reply_text = handle_onboarding(user_id, text, ddb)
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )
        try:
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # PENDING_CLARIFICATION チェック（classify_intent より先に処理）
    pending_clarif = ddb.get_item(pk=pk, sk=SK_PENDING_CLARIFICATION)
    if pending_clarif:
        reply_text, items_to_save = expense_extractor.handle_clarification(
            text, user_id, pending_clarif, ddb
        )
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )
        try:
            _save_expense_items(user_id, items_to_save, ddb)
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # Intent 分類（1回呼び出し）
    intent_result = classify_intent(text)
    intent = intent_result.get("intent", "CHAT")

    # PENDING_EXPENSE チェック（確認応答処理）
    pending_expense = ddb.get_item(pk=pk, sk=SK_PENDING_EXPENSE)
    if pending_expense:
        if intent == "CONFIRM_YES":
            reply_text, items_to_save = expense_extractor.confirm_pending_expense(
                user_id, pending_expense, ddb
            )
            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            try:
                _save_expense_items(user_id, items_to_save, ddb)
                _update_daily_count(user_id, today, ddb)
            except Exception as e:
                logger.warning("post_reply_ops_failed", error=str(e))
            return
        elif intent == "CONFIRM_NO":
            reply_text = expense_extractor.reject_pending_expense(user_id, ddb)
            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            try:
                _update_daily_count(user_id, today, ddb)
            except Exception as e:
                logger.warning("post_reply_ops_failed", error=str(e))
            return
        # YES/NO 以外は待機溌けのまま通常フローへフォールスルー

    # EXPENSE intent 処理
    if intent == "EXPENSE":
        reply_text, items_to_save = expense_extractor.extract(text, user_id, ddb)
        if reply_text:  # 空文字の場合は支出でなかった→チャットフローへ
            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            try:
                _save_expense_items(user_id, items_to_save, ddb)
                _save_chat_log(user_id, text, reply_text, intent, ddb)
                _update_daily_count(user_id, today, ddb)
            except Exception as e:
                logger.warning("post_reply_ops_failed", error=str(e))
            return

    # 通常チャットフロー
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    onboarding_state = ddb.get_item(pk=pk, sk="ONBOARDING_STATE#") or {}
    onboarding_step = onboarding_state.get("step", "")

    in_onboarding = (
        intent == "ONBOARDING"
        or (onboarding_step and onboarding_step != STEP_COMPLETED)
    )

    tone = profile.get("tone", "friendly")

    # REWARD intent → ご褒美提案（スライス 5-2〜5-6）
    if intent == "REWARD" and not in_onboarding:
        emotion_info = _infer_emotion(text)
        reply_text = reward_proposal_handler.propose_reward(
            user_id=user_id,
            text=text,
            ddb=ddb,
            tone=tone,
            emotion=emotion_info["emotion"],
            fatigue_level=emotion_info["fatigue_level"],
        )
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )
        try:
            _save_chat_log(user_id, text, reply_text, intent, ddb)
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    if in_onboarding:
        reply_text = handle_onboarding(user_id, text, ddb)
    else:
        reply_text = generate_reply(
            user_id=user_id,
            intent_result=intent_result,
            text=text,
            ddb_service=ddb,
            tone=tone,
        )

    get_line_service().reply_message(
        reply_token, [{"type": "text", "text": reply_text}]
    )

    try:
        _save_chat_log(user_id, text, reply_text, intent, ddb)
        _update_daily_count(user_id, today, ddb)
        _detect_preferences(user_id, text, ddb)
    except Exception as e:
        logger.warning("post_reply_ops_failed", error=str(e))


def _handle_image(user_id, message_id, reply_token):
    """画像メッセージを受け取り、レシート解析を行う。"""
    ddb = _get_ddb()
    try:
        image_bytes = get_line_service().get_message_content(message_id)
    except Exception as e:
        logger.warning("get_message_content_failed", error=str(e))
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": "画像を取得できなかったよ😅テキストで教えてくれると嬉しいな！"}]
        )
        return

    reply_text, items_to_save = receipt_analyzer.analyze(
        image_bytes=image_bytes,
        content_type="image/jpeg",
        user_id=user_id,
        ddb=ddb,
    )
    get_line_service().reply_message(
        reply_token, [{"type": "text", "text": reply_text}]
    )
    try:
        _save_expense_items(user_id, items_to_save, ddb)
    except Exception as e:
        logger.warning("post_reply_ops_failed", error=str(e))


def _save_expense_items(user_id: str, items: list[dict], ddb: DynamoDBService) -> None:
    """支出アイテムを DynamoDB に保存し月次サマリーを更新する。"""
    if not items:
        return
    pk = f"USER#{user_id}"
    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    month_sk = f"MONTHLY_SUMMARY#{now.strftime('%Y-%m')}"

    # プロフィールから reward_budget_monthly を取得
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    reward_budget = int(profile.get("reward_budget_monthly", 30_000))

    for item in items:
        expense_sk = f"EXPENSE#{ts}_{id(item)}"
        ddb.put_item(pk, expense_sk, {
            "entityType": "EXPENSE",
            "item_name": item.get("item_name"),
            "amount": item.get("amount", 0),
            "store_name": item.get("store_name"),
            "ars_category": item.get("category"),
            "source": item.get("source", "text"),
            "confidence": item.get("confidence", 1.0),
            "created_at": ts,
        })
        amount = int(item.get("amount") or 0)
        if amount > 0:
            ddb.add_to_monthly_summary(
                pk=pk,
                month_sk=month_sk,
                amount=amount,
                reward_budget=reward_budget,
                updated_at=ts,
            )


def _save_chat_log(user_id, user_text, reply_text, intent, ddb):
    now = datetime.now(timezone.utc)
    pk = f"USER#{user_id}"
    ttl = int((now + timedelta(days=30)).timestamp())
    ts = now.isoformat()
    ddb.put_item(pk, f"CHAT#{ts}_user", {
        "role": "user", "message": user_text,
        "intent": intent, "createdAt": ts, "ttl": ttl,
    })
    ddb.put_item(pk, f"CHAT#{ts}_assistant", {
        "role": "assistant", "message": reply_text,
        "createdAt": ts, "ttl": ttl,
    })


def _update_daily_count(user_id, today, ddb):
    pk = f"USER#{user_id}"
    sk = f"DAILY_COUNT#{today}"
    tomorrow = datetime.now(timezone.utc).replace(
        hour=1, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    ttl = int(tomorrow.timestamp())
    ddb.increment_atomic_counter(pk=pk, sk=sk, attribute="count", ttl=ttl)


def _detect_preferences(user_id, text, ddb):
    _KEYWORDS = {
        "スイーツ": ["ケーキ", "プリン", "チョコ", "アイス", "パフェ"],
        "カフェ": ["カフェ", "コーヒー", "ラテ", "紅茶"],
        "旅行": ["旅行", "温泉", "ホテル", "旅館"],
        "読書": ["本", "読書", "漫画", "小説"],
        "美容": ["コスメ", "スキンケア", "ネイル", "マッサージ"],
        "グルメ": ["ランチ", "ディナー", "レストラン", "居酒屋", "ラーメン"],
    }
    detected = [cat for cat, kws in _KEYWORDS.items() if any(kw in text for kw in kws)]
    if not detected:
        return
    pk = f"USER#{user_id}"
    existing_raw = ddb.get_item(pk=pk, sk="PREF_MEMORY#")
    existing = existing_raw or {}
    categories = existing.get("categories", [])
    new_categories = list(set(categories + detected))
    if len(new_categories) != len(categories):
        now = datetime.now(timezone.utc).isoformat()
        if existing_raw is None:
            ddb.put_item(pk, "PREF_MEMORY#", {
                "entityType": "PREF_MEMORY",
                "categories": new_categories,
                "updatedAt": now,
            })
        else:
            ddb.update_item(pk=pk, sk="PREF_MEMORY#", updates={"categories": new_categories, "updatedAt": now})


def _handle_error(event, error):
    logger.exception("event_processing_error", error_type=type(error).__name__)
    reply_token = event.get("replyToken")
    if not reply_token:
        return
    try:
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": ERROR_REPLY}]
        )
    except Exception:
        logger.warning("fallback_reply_failed")
