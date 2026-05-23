"""
ご褒美提案ハンドラー（Unit 5）

設計方針:
- DynamoDB からご褒美候補プール・プロファイルを取得
- finance_engine で今月の余裕額を算出（スライス 5-1）
- 余裕額 <= 0 の場合はやんわり止めメッセージを返す（スライス 5-5）
- 余裕額以内の候補をスコア降順で最大 PROPOSAL_MAX_CANDIDATES 件に絞り込む（スライス 5-2, 5-3）
- Bedrock Nova Micro でキャラクター口調の提案文を生成（スライス 5-4）
- 提案履歴を REWARD_SUGGESTION# に保存（スライス 5-6）
- Google Calendar 連携済みユーザーはカレンダーコンテキストを注入（スライス 5-8）
- 候補なし / Bedrock 失敗時はフォールバックメッセージを返す
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from models.schemas import (
    ENTITY_REWARD_SUGGESTION,
    SK_PREFIX_REWARD_POOL,
    SK_PREFIX_REWARD_SUGGESTION,
    RewardPoolItem,
)
from prompts.reward_proposal_prompt import (
    REWARD_PROPOSAL_SYSTEM,
    build_reward_proposal_prompt,
    build_stop_reply,
)
from services.bedrock_service import BedrockService
from services.dynamodb_service import DynamoDBService
from services.finance_engine import calculate_slack
from services.google_calendar_service import GoogleCalendarService
from utils.exceptions import BedrockError
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
MAX_CANDIDATES = int(os.environ.get("PROPOSAL_MAX_CANDIDATES", "5"))
_JST = timezone(timedelta(hours=9))

# フォールバックメッセージ（候補なし）
_FALLBACK_NO_ITEMS: dict[str, str] = {
    "friendly": "うーん、今ちょうどいいご褒美が見つからなかったんだ〜🌿 また明日見てみるねぇ",
    "polite": "うーん、今ちょうどいいご褒美が見つからなかったんだ〜🌿 また明日見てみるねぇ",
    "devilish": "うーん、今ちょうどいいご褒美が見つからなかったんだ〜🌿 また明日見てみるねぇ",
}

# フォールバックメッセージ（Bedrock 失敗）
_FALLBACK_BEDROCK: dict[str, str] = {
    "friendly": "んー、ちょっとフリーズしちゃった🌿 でもご褒美候補は見つかってるよ〜。また話しかけてねぇ",
    "polite": "んー、ちょっとフリーズしちゃった🌿 でもご褒美候補は見つかってるよ〜。また話しかけてねぇ",
    "devilish": "んー、ちょっとフリーズしちゃった🌿 でもご褒美候補は見つかってるよ〜。また話しかけてねぇ",
}

# ─────────────────────────────────────────
# モジュールレベルシングルトン
# ─────────────────────────────────────────
_bedrock = BedrockService()
_calendar_service = GoogleCalendarService()


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────

def _load_reward_pool(user_id: str, ddb: DynamoDBService) -> list[RewardPoolItem]:
    """DynamoDB からご褒美候補プールを取得する"""
    pk = f"USER#{user_id}"
    try:
        item = ddb.get_item(pk=pk, sk=SK_PREFIX_REWARD_POOL)
        if not item:
            return []
        raw_items = item.get("items") or []
        result: list[RewardPoolItem] = []
        for raw in raw_items:
            try:
                result.append(RewardPoolItem(**raw))
            except Exception as e:
                logger.warning("reward_pool_item_parse_error", error=str(e))
        return result
    except Exception as e:
        logger.warning("load_reward_pool_failed", error=str(e))
        return []


def _filter_candidates(
    pool: list[RewardPoolItem],
    slack: Decimal,
    max_count: int = MAX_CANDIDATES,
) -> list[RewardPoolItem]:
    """余裕額以内の候補をスコア降順で絞り込む"""
    affordable = [item for item in pool if item.price <= slack]
    affordable.sort(key=lambda x: x.score, reverse=True)
    return affordable[:max_count]


def _build_calendar_context(events: list[dict]) -> Optional[str]:
    """
    カレンダーイベントをプロンプト用コンテキスト文字列に変換する。

    イベントのサマリー（タイトル）のみを使用し、
    内容・参加者・場所等は含めない（SEC-08 準拠）。

    Args:
        events: Google Calendar API から取得したイベントリスト

    Returns:
        コンテキスト文字列（イベントなし / タイトルなし の場合は None）
    """
    if not events:
        return None
    summaries = []
    for event in events[:3]:  # 最大 3 件
        summary = event.get("summary") or ""
        if summary:
            summaries.append(summary)
    if not summaries:
        return None
    return "今日の予定: " + "、".join(summaries)


def _save_suggestion(
    user_id: str,
    item: Optional[RewardPoolItem],
    ddb: DynamoDBService,
) -> None:
    """提案履歴を DynamoDB REWARD_SUGGESTION# に保存する"""
    now = datetime.now(_JST).isoformat()
    sk = f"{SK_PREFIX_REWARD_SUGGESTION}{now}"
    pk = f"USER#{user_id}"
    record: dict = {
        "entity_type": ENTITY_REWARD_SUGGESTION,
        "proposed_at": now,
    }
    if item:
        record["item_id"] = item.id
        record["item_name"] = item.name
        record["price"] = str(item.price)
    try:
        ddb.put_item(pk=pk, sk=sk, item=record)
    except Exception as e:
        logger.warning("save_suggestion_failed", error=str(e))


# ─────────────────────────────────────────
# 公開関数
# ─────────────────────────────────────────

def propose_reward(
    user_id: str,
    text: str,
    ddb: DynamoDBService,
    tone: str = "friendly",
    emotion: str = "neutral",
    fatigue_level: int = 0,
) -> str:
    """
    ご褒美提案メインロジック。

    処理フロー:
      1. プロファイル取得 → 余裕額算出
      2. 余裕額 <= 0 → やんわり止めを返す
      3. ご褒美候補プール取得 → 余裕額内で絞り込み
      4. 候補なし → フォールバックを返す
      5. Google Calendar コンテキスト取得（連携済みのみ）
      6. プロンプト構築 → Bedrock 呼び出し
      7. 提案履歴を DynamoDB に保存
      8. 返信テキストを返す

    Args:
        user_id:       LINE ユーザー ID
        text:          ユーザーのメッセージ本文
        ddb:           DynamoDB サービスインスタンス
        tone:          ふれまーるちゃんの口調（friendly / polite / devilish）
        emotion:       感情推定結果（neutral / tired / happy / stressed / angry）
        fatigue_level: 疲労度（0〜5）

    Returns:
        ふれまーるちゃんの返信テキスト
    """
    pk = f"USER#{user_id}"

    # プロファイル取得
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}

    # 余裕額算出（繰り越し込みの total_budget を使用: F2-07）
    slack, total_budget = calculate_slack(user_id=user_id, ddb=ddb, profile=profile)

    # 余裕額 0 以下 → やんわり止め（スライス 5-5）
    if slack <= Decimal("0"):
        logger.info("propose_reward_stopped", reason="slack_exhausted")
        _save_suggestion(user_id, None, ddb)
        return build_stop_reply(tone)

    # ご褒美候補プール取得（スライス 5-2）
    pool = _load_reward_pool(user_id, ddb)

    # 余裕額内で絞り込み（スライス 5-3）
    candidates = _filter_candidates(pool, slack)

    if not candidates:
        logger.info("propose_reward_no_candidates")
        return _FALLBACK_NO_ITEMS.get(tone, _FALLBACK_NO_ITEMS["friendly"])

    # Google Calendar コンテキスト取得（スライス 5-8）
    calendar_context: Optional[str] = None
    try:
        if _calendar_service.is_connected(user_id):
            events = _calendar_service.get_today_events(user_id)
            calendar_context = _build_calendar_context(events)
    except Exception as e:
        logger.warning("calendar_context_failed", error=str(e))

    # プロンプト構築（スライス 5-4）
    candidate_dicts = [
        {
            "name": c.name,
            "price": c.price,
            "source_url": c.source_url or "",
            "type": c.type,
        }
        for c in candidates
    ]

    prompt = build_reward_proposal_prompt(
        user_message=text,
        slack=slack,
        candidates=candidate_dicts,
        emotion=emotion,
        fatigue_level=fatigue_level,
        calendar_context=calendar_context,
        tone=tone,
    )

    # Bedrock 呼び出し（スライス 5-4）
    try:
        reply_text = _bedrock.invoke_text(
            prompt=prompt,
            system_prompt=REWARD_PROPOSAL_SYSTEM,
            max_tokens=500,
            temperature=0.8,
        )
    except BedrockError as e:
        logger.warning("reward_proposal_bedrock_error", error=str(e))
        reply_text = _FALLBACK_BEDROCK.get(tone, _FALLBACK_BEDROCK["friendly"])

    # 提案履歴保存（スライス 5-6）
    _save_suggestion(user_id, candidates[0], ddb)

    return reply_text
