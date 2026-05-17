"""
月次レポート生成 — Flex Message で今月のサマリーを返す

postback action=monthly_summary で呼ばれる。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from services.dynamodb_service import DynamoDBService
from services.finance_engine import get_reward_budget
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))


def generate_monthly_report(user_id: str, ddb: DynamoDBService) -> list[dict]:
    """今月のごほうびレポートを Flex Message で生成する"""
    pk = f"USER#{user_id}"
    now = datetime.now(_JST)
    month_str = now.strftime("%Y-%m")

    # データ取得
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    month_sk = f"MONTHLY_SUMMARY#{month_str}"
    summary = ddb.get_item(pk=pk, sk=month_sk) or {}

    budget = int(get_reward_budget(profile))
    total_budget = int(summary.get("total_budget", budget))
    if total_budget == 0:
        total_budget = budget
    spent = int(summary.get("total_amount", 0))
    remaining = max(total_budget - spent, 0)
    expense_count = int(summary.get("expense_count", 0))
    carryover = int(summary.get("carryover_amount", 0))

    # 使用率計算
    usage_pct = min(int((spent / total_budget * 100) if total_budget > 0 else 0), 100)
    bar_filled = usage_pct // 10
    bar_empty = 10 - bar_filled
    progress_bar = "█" * bar_filled + "░" * bar_empty

    # 繰り越し見込み（carryover_rate はプロフィールから）
    carryover_rate = float(profile.get("carryover_rate", 0.5))
    carryover_forecast = int(remaining * carryover_rate)

    # カテゴリ別集計
    expenses = ddb.query_by_pk(pk=pk, sk_prefix=f"EXPENSE#{month_str}", limit=100)
    category_totals: dict[str, int] = {}
    for exp in expenses:
        cat = exp.get("ars_category") or exp.get("item_name") or "その他"
        amt = int(exp.get("amount", 0))
        category_totals[cat] = category_totals.get(cat, 0) + amt

    # 上位4カテゴリ
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:4]

    # 月表示
    month_label = f"{now.month}月"

    # コメント生成
    if usage_pct < 30:
        comment = "まだまだ余裕あるね〜✨\n何かごほうびしちゃう？🎀"
    elif usage_pct < 60:
        comment = "いい感じのペースだね😊\nまだ余裕あるよ〜✨"
    elif usage_pct < 80:
        comment = "けっこう使ってるね〜😅\nあと少し気をつけようか💪"
    else:
        comment = "今月はがんばったね…！\n来月に繰り越し分で楽しもう🎀"

    # Flex Message 構築
    body_contents = [
        {"type": "text", "text": f"📊 {month_label}のごほうびレポート", "weight": "bold", "size": "lg", "color": "#FF6B9D"},
        {"type": "separator", "margin": "md"},
        {"type": "box", "layout": "vertical", "margin": "lg", "contents": [
            _kv_row("予算", f"{total_budget:,}円"),
            _kv_row("使った", f"{spent:,}円"),
            _kv_row("残り", f"{remaining:,}円"),
        ]},
        {"type": "text", "text": f"{progress_bar} {usage_pct}%", "size": "sm", "color": "#666666", "margin": "md"},
    ]

    if carryover > 0:
        body_contents.append(
            {"type": "text", "text": f"（うち繰り越し: {carryover:,}円）", "size": "xs", "color": "#999999", "margin": "sm"}
        )

    if sorted_cats:
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append({"type": "text", "text": "内訳:", "size": "sm", "weight": "bold", "margin": "md"})
        for cat, amt in sorted_cats:
            body_contents.append(
                {"type": "text", "text": f"  {cat}  {amt:,}円", "size": "sm", "color": "#555555"}
            )

    if carryover_forecast > 0:
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append(
            {"type": "text", "text": f"繰り越し見込み: {carryover_forecast:,}円\n(残り{remaining:,}円の{int(carryover_rate*100)}%)", "size": "xs", "color": "#999999", "margin": "sm", "wrap": True}
        )

    body_contents.append({"type": "separator", "margin": "lg"})
    body_contents.append({"type": "text", "text": comment, "size": "sm", "wrap": True, "margin": "md"})

    flex_message = {
        "type": "flex",
        "altText": f"{month_label}のごほうびレポート",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents,
            },
        },
    }

    return [flex_message]


def _kv_row(label: str, value: str) -> dict:
    """キー・バリュー行を Flex Box で作成"""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": "#666666", "flex": 2},
            {"type": "text", "text": value, "size": "sm", "weight": "bold", "align": "end", "flex": 3},
        ],
    }
