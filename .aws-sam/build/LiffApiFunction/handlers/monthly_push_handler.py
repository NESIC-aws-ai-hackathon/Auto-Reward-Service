"""
月初レポート Push ハンドラー — 毎月 1 日 JST 9:00 起動

責務:
  1. 全 ACTIVE ユーザーを取得
  2. 先月の MONTHLY_SUMMARY から繰り越し計算
  3. レポートメッセージ生成 + Push 送信
  4. push_count_this_month リセット
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from models.schemas import ENTITY_PROFILE, SK_PUSH_SETTINGS, SK_PREFIX_MONTHLY_SUMMARY
from services.dynamodb_service import get_dynamodb_service
from services.finance_engine import calculate_monthly_budget, get_reward_budget, get_monthly_spending
from services.push_manager import send_push, reset_monthly_push_count
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))


def handler(event: dict, context) -> dict:
    """EventBridge から毎月 1 日 JST 9:00 に起動される"""
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    logger.info("monthly_push_start")
    ddb = get_dynamodb_service()
    now_jst = datetime.now(_JST)

    # 先月の年月
    first_of_this_month = now_jst.replace(day=1)
    last_month_date = first_of_this_month - timedelta(days=1)
    last_month_str = last_month_date.strftime("%Y-%m")

    # 全 ACTIVE ユーザーを取得
    try:
        profiles = ddb.query_by_gsi(entity_type=ENTITY_PROFILE, filter_expr={"status": "ACTIVE"})
    except Exception as e:
        logger.error("monthly_push_gsi_query_failed", error=str(e))
        return {"statusCode": 500, "body": "GSI query failed"}

    sent_count = 0
    skipped_count = 0

    for profile in profiles:
        user_pk = profile.get("PK", "")
        if not user_pk.startswith("USER#"):
            continue
        user_id = user_pk.replace("USER#", "")

        # PUSH_SETTINGS チェック
        settings = ddb.get_item(pk=user_pk, sk=SK_PUSH_SETTINGS) or {}
        if not settings.get("all_enabled", True) or not settings.get("monthly_report", True):
            skipped_count += 1
            # push_count リセットは設定に関わらず実行
            reset_monthly_push_count(user_id, ddb)
            continue

        # 先月の MONTHLY_SUMMARY 取得
        last_month_sk = f"{SK_PREFIX_MONTHLY_SUMMARY}{last_month_str}"
        summary = ddb.get_item(pk=user_pk, sk=last_month_sk) or {}

        # 予算・支出データ
        base_budget = int(get_reward_budget(profile))
        total_amount = int(summary.get("total_amount", 0))
        last_month_budget = int(summary.get("total_budget", base_budget))
        remaining = max(last_month_budget - total_amount, 0)

        # 繰り越し計算
        carryover_rate = float(profile.get("carryover_rate", 0.5))
        budget_calc = calculate_monthly_budget(
            base_budget=base_budget,
            last_month_remaining=remaining,
            carryover_rate=carryover_rate,
        )

        # レポートメッセージ生成
        nickname = profile.get("nickname") or "きみ"
        message_text = _build_monthly_report(
            nickname=nickname,
            last_budget=last_month_budget,
            last_spent=total_amount,
            last_remaining=remaining,
            carryover=budget_calc["carryover_amount"],
            new_budget=budget_calc["total_budget"],
        )

        # Push 送信
        success = send_push(
            user_id=user_id,
            message={"type": "text", "text": message_text},
            ddb=ddb,
            category="monthly_report",
            template_id="monthly_report:0",
        )

        if success:
            sent_count += 1
        else:
            skipped_count += 1

        # push_count_this_month リセット（新月の開始）
        reset_monthly_push_count(user_id, ddb)

    logger.info(
        "monthly_push_complete",
        sent=sent_count,
        skipped=skipped_count,
        total=len(profiles),
    )

    return {
        "statusCode": 200,
        "body": f"Monthly report sent: {sent_count}, skipped: {skipped_count}",
    }


def _build_monthly_report(
    nickname: str,
    last_budget: int,
    last_spent: int,
    last_remaining: int,
    carryover: int,
    new_budget: int,
) -> str:
    """月初レポートメッセージを生成する"""
    if last_spent == 0 and last_budget == 0:
        return (
            f"ねね、{nickname}🎀\n"
            f"今月もよろしくね！\n"
            f"何かあったらいつでも話しかけてね〜✨"
        )

    usage_pct = min(int((last_spent / last_budget * 100) if last_budget > 0 else 0), 100)

    if carryover > 0:
        carryover_line = f"💰 繰り越し: {carryover:,}円（{int(carryover / max(last_remaining, 1) * 100)}%）\n"
        budget_line = (
            f"\n今月のごほうび枠は…\n"
            f"{new_budget - carryover:,}円 + {carryover:,}円 = {new_budget:,}円！🎉\n"
            f"\n先月ちゃんとセーブしたから\n"
            f"今月はちょっと贅沢できるね〜😏✨"
        )
    else:
        carryover_line = ""
        budget_line = f"\n今月のごほうび枠は {new_budget:,}円！\n今月も楽しんでいこ〜✨"

    if usage_pct <= 50:
        comment = "すごい！セーブ上手だね✨"
    elif usage_pct <= 80:
        comment = "いい感じに楽しめたね😊"
    else:
        comment = "しっかり楽しんだね！💪"

    return (
        f"ねね、{nickname}🎀\n"
        f"先月のごほうびレポートだよ📊\n"
        f"\n"
        f"✅ 予算: {last_budget:,}円\n"
        f"✅ 使った: {last_spent:,}円（{usage_pct}%）\n"
        f"💰 残り: {last_remaining:,}円\n"
        f"{carryover_line}"
        f"\n{comment}"
        f"{budget_line}"
    )
