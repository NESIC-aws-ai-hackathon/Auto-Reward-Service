"""
ストレス評価エンジン（Stress Engine）

キーワード検出ではなく、ユーザーの蓄積データを総合評価して
寄り道を提案すべきタイミングを能動的に判定する。

評価軸:
  - メッセージの感情トーン（Bedrock 評価）  : 0〜25点
  - 帰宅時間帯かどうか（17〜21時、平日）   : 0〜25点
  - 直近の「回復系」支出パターン           : 0〜25点
  - 直近チャットログのストレスシグナル     : 0〜25点
  合計 60点以上 → 寄り道を提案

スパム防止: 直近 COOLDOWN_HOURS 時間以内に提案済みなら提案しない。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta

from services.dynamodb_service import DynamoDBService
from services.bedrock_service import BedrockService
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
_bedrock = BedrockService()

COOLDOWN_HOURS = 4      # 再提案まで最低何時間空けるか
SUGGEST_THRESHOLD = 60  # 合計スコアがこれ以上なら提案

# 直近チャット検索に使うストレス語彙（弱シグナル）
_STRESS_WORDS = {
    "疲れ", "しんど", "無理", "つらい", "つらく", "きつ", "だるい",
    "眠い", "最悪", "やばい", "もう", "いやだ", "嫌だ", "帰り",
    "長かっ", "長い", "残業", "遅く", "遅い",
}

# 回復系 ARS カテゴリ
_RECOVERY_CATEGORIES = {"回復費", "情緒安定費"}


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────

def should_suggest_detour(user_id: str, message: str, ddb: DynamoDBService) -> dict:
    """
    メッセージと蓄積データを総合評価し、寄り道提案すべきかを判定する。

    Returns:
        dict: {"suggest": bool, "score": int, "reason": str}
    """
    # クールダウン中なら即返却
    if _is_in_cooldown(user_id, ddb):
        logger.info("stress_cooldown", user_id=user_id)
        return {"suggest": False, "score": 0, "reason": "cooldown"}

    # 各シグナルのスコア計算
    time_score = _calc_time_score()
    expense_score = _calc_expense_score(user_id, ddb)
    chat_score = _calc_chat_stress_score(user_id, ddb)
    message_score, bedrock_reason = _assess_message_stress(message)

    total = time_score + expense_score + chat_score + message_score

    logger.info(
        "stress_assessed",
        user_id=user_id,
        time=time_score,
        expense=expense_score,
        chat=chat_score,
        msg_score=message_score,
        total=total,
        suggest=(total >= SUGGEST_THRESHOLD),
    )

    return {
        "suggest": total >= SUGGEST_THRESHOLD,
        "score": total,
        "reason": bedrock_reason,
    }


# ─────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────

def _is_in_cooldown(user_id: str, ddb: DynamoDBService) -> bool:
    """直近 COOLDOWN_HOURS 時間以内にTEMPTATION_SESSIONが存在するかチェック。"""
    try:
        pk = f"USER#{user_id}"
        sessions = ddb.query_by_pk(pk=pk, sk_prefix="TEMPTATION_SESSION#", limit=5, descending=True)
        cutoff = datetime.now(_JST) - timedelta(hours=COOLDOWN_HOURS)
        for s in sessions:
            raw = s.get("created_at", "")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_JST)
                if dt > cutoff:
                    return True
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.warning("cooldown_check_failed", error=str(e))
    return False


def _calc_time_score() -> int:
    """帰宅時間帯スコア（最大 25点）。平日17〜21時が最高点。"""
    now = datetime.now(_JST)
    hour = now.hour
    weekday = now.weekday()  # 0=月〜4=金, 5=土, 6=日

    is_weekday = weekday < 5
    base = 5 if is_weekday else 0  # 平日ベース

    if 17 <= hour <= 21:
        return base + 20   # 帰宅ラッシュ帯
    elif 22 <= hour or hour <= 1:
        return base + 10   # 夜遅め（残業帰り）
    else:
        return base


def _calc_expense_score(user_id: str, ddb: DynamoDBService) -> int:
    """直近20件の支出に「回復系」カテゴリが多いほど高スコア（最大 25点）。"""
    try:
        pk = f"USER#{user_id}"
        recent = ddb.query_by_pk(pk=pk, sk_prefix="EXPENSE#", limit=20, descending=True)
        count = sum(1 for e in recent if e.get("ars_category") in _RECOVERY_CATEGORIES)
        return min(count * 5, 25)
    except Exception as e:
        logger.warning("expense_score_failed", error=str(e))
        return 0


def _calc_chat_stress_score(user_id: str, ddb: DynamoDBService) -> int:
    """直近5件のチャットログにストレス語彙が含まれるほど高スコア（最大 25点）。"""
    try:
        pk = f"USER#{user_id}"
        logs = ddb.query_by_pk(pk=pk, sk_prefix="CHAT#", limit=5, descending=True)
        count = 0
        for log in logs:
            user_text = log.get("user_text", "")
            if any(w in user_text for w in _STRESS_WORDS):
                count += 1
        return min(count * 5, 25)
    except Exception as e:
        logger.warning("chat_score_failed", error=str(e))
        return 0


def _assess_message_stress(message: str) -> tuple[int, str]:
    """Bedrock でメッセージの疲労・ストレス度を 0〜25点で評価する。

    Returns:
        (score, reason)
    """
    prompt = (
        "ユーザーのメッセージを読み、疲労・ストレス度を評価してください。\n\n"
        f"メッセージ: <user_message>{message}</user_message>\n\n"
        "疲労・ストレスのシグナル（直接的・間接的を問わない）を検出し、0〜25点のスコアで評価してください。\n"
        "- 0点: ストレスのシグナルなし（「ありがとう」「楽しかった」など）\n"
        "- 10点: 軽いストレスシグナル（「ちょっと疲れた」「今日は長かった」）\n"
        "- 25点: 強いストレスシグナル（「もう無理」「しんどい」「最悪」）\n\n"
        '以下のJSONのみ出力してください: {"score": <0-25の整数>, "reason": "<10文字以内の判断理由>"}'
    )
    try:
        raw = _bedrock.invoke_text(prompt, max_tokens=100, temperature=0.2)
        m = re.search(r"\{[^}]+\}", raw)
        if m:
            data = json.loads(m.group())
            score = max(0, min(25, int(data.get("score", 0))))
            reason = str(data.get("reason", ""))
            return score, reason
    except Exception as e:
        logger.warning("bedrock_stress_failed", error=str(e))
    return 0, ""
