from __future__ import annotations

import base64
import json
import os
import random
import re
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

from services.talk_starter import generate_talk_starter
from services.recommend_flow import start_recommend, handle_recommend_reply, try_handle_last_suggestion_purchase
from services.quick_expense import show_quick_expense_options, handle_quick_expense_reply
from services.monthly_report import generate_monthly_report
from services.streak import update_streak
from services.temptation_engine import invite_location, try_complete_active_session
from services.stress_engine import should_suggest_detour

logger = get_logger(__name__)

DAILY_CHAT_LIMIT = int(os.getenv("DAILY_CHAT_LIMIT", "50"))
MAX_INPUT_LENGTH = 1000

DAILY_LIMIT_REPLY = (
    "今日はいっぱいおしゃべりしたねぇ～🌿\n"
    "ふれまーるちゃん、ちょっとのんびり休むねぇ。\n"
    "また明日、ゆっくりお話しよー✨"
)
INPUT_TOO_LONG_REPLY = (
    "うーん、ちょっと長くて読み切れなかったかも～😅\n"
    "1000文字くらいでもう一度教えてほしいなぁ～"
)

UNSUPPORTED_REPLIES = [
    "スタンプだねぇ～かわいい🌿 でも文字のほうが得意なんだぁ～",
    "んー、それはまだ読めないかも～。テキストで話しかけてくれるとうれしいなぁ",
    "おっ、気になるねぇ～！でも今はテキストだけ対応してるんだ～🌱",
]

ERROR_REPLY = "んー、ちょっと調子がよくないみたい…🌿 またあとで話しかけてねぇ～"

_ddb = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event, context):
    if event.get("source") == "warmup":
        # コールドスタート後の最初のリクエストを高速化するためサービス接続を事前初期化
        try:
            get_line_service()
            _get_ddb()
        except Exception:
            pass
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
    elif event_type == "postback":
        _handle_postback(event)
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

    # RECOMMEND_STATE チェック（おすすめフロー中間状態）
    recommend_state = ddb.get_item(pk=pk, sk="RECOMMEND_STATE#")
    if recommend_state and recommend_state.get("step"):
        messages = handle_recommend_reply(user_id, text, recommend_state, ddb)
        get_line_service().reply_message(reply_token, messages)
        try:
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # QUICK_EXPENSE_STATE チェック（クイック支出入力中間状態）
    quick_state = ddb.get_item(pk=pk, sk="QUICK_EXPENSE_STATE#")
    if quick_state and quick_state.get("step"):
        messages, items_to_save = handle_quick_expense_reply(user_id, text, quick_state, ddb)
        get_line_service().reply_message(reply_token, messages)
        try:
            _save_expense_items(user_id, items_to_save, ddb)
            if items_to_save:
                streak_msg = update_streak(user_id, ddb)
                if streak_msg:
                    logger.info("streak_achieved", user_id=user_id, message=streak_msg)
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # LAST_SUGGESTION チェック — 直前のおすすめ提案 + 「買った」テキストで支出記録に直行
    try:
        last_sug_messages = try_handle_last_suggestion_purchase(user_id, text, ddb)
    except Exception as e:
        logger.warning("last_suggestion_check_failed", error=str(e))
        last_sug_messages = None
    if last_sug_messages:
        get_line_service().reply_message(reply_token, last_sug_messages)
        try:
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
            # 寄り道キーワードがあれば、直近のacceptedセッションを自動完了する
            detour_keywords = ["寄り道", "寄った", "寄っちゃった", "さっきの", "立ち寄"]
            is_detour_expense = any(kw in text for kw in detour_keywords)
            detour_place = None
            if is_detour_expense:
                try:
                    amount = items_to_save[0].get("amount", 0) if items_to_save else 0
                    item_name = items_to_save[0].get("item_name", "") if items_to_save else ""
                    detour_place = try_complete_active_session(user_id, item_name, amount, ddb)
                except Exception as e:
                    logger.warning("temptation_auto_complete_failed", error=str(e))

            if detour_place:
                reply_text += f"\n\n🌿 寄り道セッションも記録したよ〜。おつかれさま〜"

            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            try:
                _save_expense_items(user_id, items_to_save, ddb)
                streak_msg = update_streak(user_id, ddb)
                if streak_msg:
                    logger.info("streak_achieved", user_id=user_id, message=streak_msg)
                _save_chat_log(user_id, text, reply_text, intent, ddb)
                _update_daily_count(user_id, today, ddb)
                # 小間籠〬の経験が級がっていないかストレス評価
                _maybe_push_detour(user_id, text, ddb)
            except Exception as e:
                logger.warning("post_reply_ops_failed", error=str(e))

    # EXPENSE_CORRECTION intent 処理（支出金額の手動修正）
    if intent == "EXPENSE_CORRECTION":
        reply_text = expense_extractor.handle_expense_correction(text, user_id, ddb)
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )
        try:
            _save_chat_log(user_id, text, reply_text, intent, ddb)
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # PROFILE_UPDATE intent 処理（収入変更・固定費追加削除・記念日追加）
    if intent == "PROFILE_UPDATE":
        from services.profile_updater import handle_profile_update
        reply_text = handle_profile_update(user_id, text, ddb)
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": reply_text}]
        )
        try:
            _save_chat_log(user_id, text, reply_text, intent, ddb)
            _update_daily_count(user_id, today, ddb)
        except Exception as e:
            logger.warning("post_reply_ops_failed", error=str(e))
        return

    # TEMPTATION intent 処理（寄り道レーン提案）
    if intent == "TEMPTATION":
        messages = invite_location(user_id, text)
        get_line_service().reply_message(reply_token, messages)
        try:
            _save_chat_log(user_id, text, "寄り道レーン提案", intent, ddb)
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

    # ─── 購入意図判定（アクティブなレコメンドがある場合） ───
    if not in_onboarding:
        reply_text = _handle_purchase_intent_if_active(user_id, text, ddb)
        if reply_text:
            get_line_service().reply_message(
                reply_token, [{"type": "text", "text": reply_text}]
            )
            try:
                _save_chat_log(user_id, text, reply_text, "PURCHASE_INTENT", ddb)
                _update_daily_count(user_id, today, ddb)
            except Exception as e:
                logger.warning("post_reply_ops_failed", error=str(e))
            return

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
        _detect_anniversary(user_id, text, ddb)
        # チャット内容・蒙積データを総合評価して寄り道を能動的に提案
        _maybe_push_detour(user_id, text, ddb)
    except Exception as e:
        logger.warning("post_reply_ops_failed", error=str(e))


def _handle_image(user_id, message_id, reply_token):
    """画像メッセージを受け取り、SQS 経由でレシート解析を非同期実行する（Unit 3 スライス 3-6）"""
    queue_url = os.getenv("RECEIPT_QUEUE_URL", "")

    if queue_url:
        # 非同期処理: SQS にジョブを投入し即返答
        try:
            import boto3
            sqs = boto3.client("sqs")
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"user_id": user_id, "message_id": message_id}),
            )
            get_line_service().reply_message(
                reply_token,
                [{"type": "text", "text": "レシート受け取ったよ〜🌿 ちょっと時間かかるかもだけど、解析できたらお知らせするねぇ"}],
            )
        except Exception as e:
            logger.warning("sqs_send_failed", error=str(e))
            _handle_image_sync(user_id, message_id, reply_token)
    else:
        # SQS 未設定時は同期処理（ローカル開発・テスト用）
        _handle_image_sync(user_id, message_id, reply_token)


def _handle_image_sync(user_id, message_id, reply_token):
    """レシート画像を同期処理する（フォールバック）"""
    ddb = _get_ddb()
    try:
        image_bytes = get_line_service().get_message_content(message_id)
    except Exception as e:
        logger.warning("get_message_content_failed", error=str(e))
        get_line_service().reply_message(
            reply_token, [{"type": "text", "text": "画像を取得できなかったよ〜🌿 テキストで教えてくれるとうれしいなぁ"}]
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


def _maybe_push_detour(user_id: str, text: str, ddb) -> None:
    """
    ストレスエンジンで総合評価し、閾値を超えたら寄り道を PWA 通知する。
    TEMPTATION intent のような明示的な要求ではなく、
    蓄積データ（時間帯・支出パターン・チャット傾向）から能動的に判定する。
    """
    try:
        from services.notification_service import create_notification
        result = should_suggest_detour(user_id, text, ddb)
        if result.get("suggest"):
            create_notification(
                user_id=user_id,
                ddb=ddb,
                notification_type="detour_suggest",
                title="寄り道してみない？",
                message_text="お疲れがたまってるみたいだねぇ～。ちょっと寄り道して、のんびりリフレッシュしよ～🌿",
            )
            logger.info(
                "proactive_detour_notified",
                user_id=user_id,
                score=result.get("score"),
                reason=result.get("reason"),
            )
    except Exception as e:
        logger.warning("maybe_push_detour_failed", error=str(e))


def _detect_preferences(user_id, text, ddb):
    _KEYWORDS = {
        "スイーツ": ["ケーキ", "プリン", "チョコ", "アイス", "パフェ", "タルト", "マカロン", "ドーナツ", "クレープ"],
        "カフェ": ["カフェ", "コーヒー", "ラテ", "紅茶", "抹茶", "スタバ", "タリーズ", "ドトール"],
        "旅行": ["旅行", "温泉", "ホテル", "旅館"],
        "読書": ["本", "読書", "漫画", "小説"],
        "美容": ["コスメ", "スキンケア", "ネイル", "マッサージ", "エステ"],
        "グルメ": ["ランチ", "ディナー", "レストラン", "居酒屋", "ラーメン", "焼肉", "寿司", "パスタ", "カレー", "うどん", "そば", "中華", "イタリアン", "フレンチ", "定食"],
        "お酒": ["ビール", "ワイン", "日本酒", "焼酎", "ハイボール", "カクテル", "飲み"],
    }
    # 具体的な食べ物/ジャンル好みも検出
    _FOOD_LIKES_KW = [
        "ラーメン", "カフェ", "コーヒー", "スイーツ", "ケーキ", "パン",
        "焼肉", "寿司", "イタリアン", "フレンチ", "中華", "カレー",
        "パスタ", "うどん", "そば", "定食", "ハンバーガー", "ピザ",
        "タピオカ", "クレープ", "パフェ", "抹茶", "紅茶", "お酒",
        "ビール", "ワイン", "居酒屋", "バー", "ダイニング",
    ]
    detected_cats = [cat for cat, kws in _KEYWORDS.items() if any(kw in text for kw in kws)]
    detected_food = [kw for kw in _FOOD_LIKES_KW if kw in text]
    if not detected_cats and not detected_food:
        return
    pk = f"USER#{user_id}"
    existing_raw = ddb.get_item(pk=pk, sk="PREF_MEMORY#")
    existing = existing_raw or {}
    categories = existing.get("categories", [])
    food_likes = existing.get("food", {}).get("likes", []) if isinstance(existing.get("food"), dict) else []
    new_categories = list(set(categories + detected_cats))
    new_food_likes = list(set(food_likes + detected_food))
    changed = (len(new_categories) != len(categories)) or (len(new_food_likes) != len(food_likes))
    if changed:
        now = datetime.now(timezone.utc).isoformat()
        food_data = {"likes": new_food_likes}
        if existing_raw is None:
            ddb.put_item(pk, "PREF_MEMORY#", {
                "entityType": "PREF_MEMORY",
                "categories": new_categories,
                "food": food_data,
                "updatedAt": now,
            })
        else:
            ddb.update_item(pk=pk, sk="PREF_MEMORY#", updates={
                "categories": new_categories,
                "food": food_data,
                "updatedAt": now,
            })


# 記念日検知パターン（Unit 2 スライス 2-9）
_ANNIVERSARY_PATTERNS = [
    (r"(?:自分の|私の)?誕生日[はが]?\s*(\d{1,2})月(\d{1,2})日", "誕生日"),
    (r"結婚記念日[はが]?\s*(\d{1,2})月(\d{1,2})日", "結婚記念日"),
    (r"付き合[っい]た?記念日[はが]?\s*(\d{1,2})月(\d{1,2})日", "付き合った記念日"),
    (r"(?:彼女|彼氏|パートナー)[のさん]*誕生日[はが]?\s*(\d{1,2})月(\d{1,2})日", "パートナー誕生日"),
    (r"(?:子ども|子供|息子|娘)[のさん]*誕生日[はが]?\s*(\d{1,2})月(\d{1,2})日", "子どもの誕生日"),
]


def _detect_anniversary(user_id: str, text: str, ddb: DynamoDBService) -> None:
    """会話から記念日情報を自然に検知し PROFILE# の anniversaries に保存する（Unit 2 スライス 2-9）"""
    pk = f"USER#{user_id}"
    for pattern, name in _ANNIVERSARY_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                month, day = int(m.group(1)), int(m.group(2))
            except (IndexError, ValueError):
                continue
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            date_str = f"{month:02d}-{day:02d}"
            profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
            anniversaries = list(profile.get("anniversaries", []))
            for a in anniversaries:
                if a.get("name") == name:
                    if a.get("date") == date_str:
                        return
                    a["date"] = date_str
                    break
            else:
                anniversaries.append({"name": name, "date": date_str})
            now = datetime.now(timezone.utc).isoformat()
            ddb.update_item(pk=pk, sk="PROFILE#", updates={
                "anniversaries": anniversaries, "updatedAt": now,
            })
            logger.info("anniversary_detected", user_id=user_id, anniversary_name=name, date=date_str)
            return  # 1件ヒットしたら終了


def _handle_postback(event):
    """postback イベントを処理する（リッチメニューボタン等）"""
    postback_data = (event.get("postback") or {}).get("data", "")
    reply_token = event.get("replyToken", "")
    user_id = (event.get("source") or {}).get("userId", "")

    if not reply_token or not user_id:
        return

    # data=action=xxx をパース
    params = {}
    for pair in postback_data.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v

    action = params.get("action", "")
    ddb = _get_ddb()

    try:
        if action == "start_talk":
            # 変更依頼書_2 §2: 直近の通知内容から会話開始
            reply_text = _start_talk_with_context(user_id, ddb)
            if reply_text:
                get_line_service().reply_message(reply_token, [{"type": "text", "text": reply_text}])
            else:
                messages = generate_talk_starter(user_id, ddb)
                get_line_service().reply_message(reply_token, messages)

        elif action == "start_recommend":
            messages = start_recommend(user_id, ddb)
            get_line_service().reply_message(reply_token, messages)

        elif action == "quick_expense":
            from services.quick_expense import start_quick_expense_state
            messages = show_quick_expense_options(user_id)
            start_quick_expense_state(user_id, ddb)
            get_line_service().reply_message(reply_token, messages)

        elif action == "monthly_summary":
            messages = generate_monthly_report(user_id, ddb)
            get_line_service().reply_message(reply_token, messages)

        elif action == "interested":
            # レガシー: 旧おすすめフローの気になるボタン（互換性のため残す）
            item_name = params.get("item", "それ")
            get_line_service().reply_message(reply_token, [
                {"type": "text", "text": f"{item_name}が気になるんだねぇ～🌿 よかったら商品ページから買ってみてね〜"}
            ])

        elif action == "purchased":
            # おすすめから「買ったよ！」「行ったよ！」を押した場合
            item_name = params.get("name", "") or params.get("item", "")
            amount_str = params.get("price", "") or params.get("amount", "0")
            try:
                amount = int(amount_str)
            except (ValueError, TypeError):
                amount = 0
            if amount > 0 and item_name:
                _save_expense_items(user_id, [{"item_name": item_name, "amount": amount, "category": "ご褒美費", "source": "recommend"}], ddb)
                streak_msg = update_streak(user_id, ddb)
                reply = f"{item_name} {amount}円、記録したよぇ～🌿✨ 自分へのご褒美だねぇ〜"
                if streak_msg:
                    reply += f"\n\n{streak_msg}"
                get_line_service().reply_message(reply_token, [{"type": "text", "text": reply}])
            elif item_name:
                get_line_service().reply_message(reply_token, [{"type": "text", "text": f"{item_name}、楽しめたかなぁ～🌿✨"}])
            else:
                get_line_service().reply_message(reply_token, [{"type": "text", "text": "記録したよぇ～🌿"}])

        else:
            logger.info("unknown_postback_action", action=action)
            get_line_service().reply_message(reply_token, [
                {"type": "text", "text": "ん～？ちょっとわからなかったかも～🌿"}
            ])
    except Exception as e:
        logger.exception("postback_handler_error", action=action)
        try:
            get_line_service().reply_message(reply_token, [{"type": "text", "text": ERROR_REPLY}])
        except Exception:
            pass


# ─────────────────────────────────────────
# リッチメニュー「ふれまーるちゃんと話す」の会話開始 (§2)
# ─────────────────────────────────────────
def _start_talk_with_context(user_id: str, ddb) -> Optional[str]:
    """
    直近のアクティブ通知・レコメンド状態から会話を開始する。
    該当なければ None → 通常の talk_starter へフォールスルー。
    """
    try:
        from services.notification_service import get_latest_actionable_notification
        from services.recommendation_engine import get_active_recommendation

        notif = get_latest_actionable_notification(user_id, ddb)
        if notif:
            # 通知内容から会話開始
            msg = notif.get("message_text", "")
            if msg:
                return f"さっき通知したやつだね〜。\n\n{msg}"

        rec = get_active_recommendation(user_id, ddb)
        if rec:
            status = rec.get("status", "")
            title = rec.get("title", "")
            reason = rec.get("reason_text", "")

            if status == "CART_ADDED":
                return (
                    f"さっき通知したやつだね〜。\n\n"
                    f"ほしい物リストで熟成していた {title}、\n"
                    f"今のあなたにちょうどよさそうだったから、\n"
                    f"買い物かごに入れておいたよ～\n\n"
                    f"買うって言ったら買っちゃうけど、どうする〜？"
                )
            elif status == "PURCHASE_CONFIRMATION_REQUIRED":
                return (
                    f"{title} の購入確認中だったねぇ〜\n\n"
                    f"「この商品を購入して」って言ってくれたら買ってくるよ〜"
                )
            elif status in ("WAITING_USER_DECISION",):
                return (
                    f"{title} について確認中だよ〜。\n"
                    f"どうする〜？買う？やめる？"
                )
    except Exception as e:
        logger.warning("start_talk_with_context_failed", error=str(e))

    return None


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


# ─────────────────────────────────────────
# 購入意図判定（アクティブレコメンド連携）
# ─────────────────────────────────────────
def _handle_purchase_intent_if_active(user_id: str, text: str, ddb) -> Optional[str]:
    """
    アクティブなレコメンドがある場合、購入意図を判定して処理する。
    該当しなければ None を返す。
    """
    from services.purchase_intent import classify_purchase_intent
    from services.recommendation_engine import get_active_recommendation, update_recommendation_status
    from services.cart_job_service import create_cart_job

    rec = get_active_recommendation(user_id, ddb)
    if not rec:
        return None

    rec_status = rec.get("status", "")
    rec_id = rec.get("recommendation_id", "")
    product_title = rec.get("title", "")

    # CART_ADDED / WAITING_USER_DECISION / PURCHASE_CONFIRMATION_REQUIRED 状態のみ意図判定
    actionable_statuses = {"CART_ADDED", "WAITING_USER_DECISION", "PURCHASE_CONFIRMATION_REQUIRED"}
    if rec_status not in actionable_statuses:
        return None

    intent = classify_purchase_intent(text, product_title)

    if intent == "DECLINE":
        update_recommendation_status(user_id, rec_id, "DECLINED", ddb)
        # カートから削除ジョブ
        if rec_status == "CART_ADDED":
            create_cart_job(
                user_id, rec_id, "REMOVE_FROM_CART", ddb,
                product_url=rec.get("product_url"),
                expected_product_title=product_title,
            )
        return (
            "わかったよぇ～。\n"
            "かごから出して、欲望熟成庫に戻しとくねぇ。\n"
            "また必要そうな日に持ってくるねぇ～🌿"
        )

    elif intent == "AMBIGUOUS_BUY":
        update_recommendation_status(user_id, rec_id, "PURCHASE_CONFIRMATION_REQUIRED", ddb)
        return (
            "買いたい気持ちはわかったよぇ～🌿\n"
            "購入するってことだねぇ～！\n\n"
            "それじゃあ、もう一度\n"
            "「この商品を購入して」\n"
            "と送ってくれたら、買ってくるよぇ～～"
        )

    elif intent == "EXPLICIT_PURCHASE":
        update_recommendation_status(user_id, rec_id, "PURCHASE_APPROVED", ddb)
        create_cart_job(
            user_id, rec_id, "PURCHASE", ddb,
            product_url=rec.get("product_url"),
            expected_product_title=product_title,
            expected_price=rec.get("price"),
            explicit_approval_text=text,
        )
        return "承認確認したよぇ～🌿\n購入処理に進むねぇ。"

    return None
