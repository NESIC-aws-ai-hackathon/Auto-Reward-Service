"""
寄り道レーンエンジン（Temptation Engine）

ユーザーの残予算・嗜好・現在地に基づき、帰り道の寄り道レーンを生成する。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import os

from services.dynamodb_service import DynamoDBService
from services.location_service import search_nearby_places
from services.finance_engine import calculate_slack, get_monthly_spending, get_reward_budget
from services.bedrock_service import BedrockService
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
_bedrock = BedrockService()

# PWA URL（環境変数 or デフォルト）
PWA_BASE_URL = os.environ.get("PWA_BASE_URL", "https://liff.line.me/2010106872-9t0gN1D6/temptation")
LIFF_TEMPTATION_URL = PWA_BASE_URL  # 後方互換

# ホットペッパー lane_type → 検索キーワード
_LANE_TYPE_KEYWORDS: dict[str, str] = {
    "CAFE_REBOOT": "カフェ コーヒー",
    "CONVENIENCE_RECOVERY": "",  # コンビニはホットペッパーに少ないのでスキップ
    "SELF_COOKING_ESCAPE": "ラーメン 定食",
    "LOW_COST_RECOVERY": "",
    "RICHER_ESCAPE": "レストラン ダイニング",
}

# ─────────────────────────────────────────
# レーン定義
# ─────────────────────────────────────────
LANE_DEFINITIONS = {
    "CAFE_REBOOT": {
        "title": "カフェ再起動レーン ☕",
        "estimated_min": 500,
        "estimated_max": 900,
        "ars_category": "情緒安定費",
    },
    "CONVENIENCE_RECOVERY": {
        "title": "コンビニ回復レーン 🏪",
        "estimated_min": 300,
        "estimated_max": 600,
        "ars_category": "回復費",
    },
    "SELF_COOKING_ESCAPE": {
        "title": "自炊放棄レーン 🍜",
        "estimated_min": 800,
        "estimated_max": 1500,
        "ars_category": "グルメ費",
    },
    "LOW_COST_RECOVERY": {
        "title": "低コスト回復レーン 💊",
        "estimated_min": 200,
        "estimated_max": 500,
        "ars_category": "回復費",
    },
    "RICHER_ESCAPE": {
        "title": "ちょっと贅沢レーン ✨",
        "estimated_min": 1500,
        "estimated_max": 3000,
        "ars_category": "グルメ費",
    },
}


# ─────────────────────────────────────────
# Webhook → Reply（LIFF ボタン送信）
# ─────────────────────────────────────────
def invite_location(user_id: str, message: str) -> list[dict]:
    """
    TEMPTATION intent 検出後、LIFF で現在地取得を促す Reply メッセージを生成。
    LINE Messaging API の messages 配列を返す（FlexMessage形式）。
    """
    return [
        {
            "type": "flex",
            "altText": "� 寄り道レーンを作るね〜！タップして現在地を教えてください",
            "contents": {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "� 寄り道レーン",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#7c3aed",
                        }
                    ],
                    "paddingAll": "16px",
                    "backgroundColor": "#f5f3ff",
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "今日はまっすぐ帰る日じゃないかも〜🍃",
                            "size": "md",
                            "wrap": True,
                            "margin": "md",
                        },
                        {
                            "type": "text",
                            "text": "現在地の近くから、甘やかしスポットを提案するね🌸",
                            "size": "sm",
                            "color": "#666666",
                            "wrap": True,
                            "margin": "lg",
                        },
                        {
                            "type": "separator",
                            "margin": "xl",
                        },
                        {
                            "type": "text",
                            "text": "📍 下のボタンをタップして現在地を教えてね",
                            "size": "xs",
                            "color": "#999999",
                            "wrap": True,
                            "margin": "lg",
                        },
                    ],
                    "paddingAll": "16px",
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "🗺️ 現在地から寄り道スポットを探す",
                                "uri": PWA_BASE_URL,
                            },
                            "style": "primary",
                            "color": "#7c3aed",
                            "height": "md",
                        }
                    ],
                    "paddingAll": "12px",
                },
            },
        }
    ]


# ─────────────────────────────────────────
# ─────────────────────────────────────────
# レーン生成（LIFF API から呼ばれる）
# ─────────────────────────────────────────
# ジャンル→ホットペッパーキーワード変換
_GENRE_TO_KEYWORD: dict[str, str] = {
    "カフェ": "カフェ コーヒー",
    "スイーツ": "スイーツ ケーキ パフェ",
    "ラーメン": "ラーメン つけ麺",
    "定食": "定食 ごはん 和食",
    "パン": "パン ベーカリー",
    "居酒屋": "居酒屋 バー ダイニング",
    "コンビニ": "",
}


def build_lanes(user_id: str, lat: float, lng: float, message: str, ddb: DynamoDBService, *, genre: str = "") -> dict:
    """
    現在地・残予算・嗜好から寄り道レーンを3件生成する。
    genre が指定された場合、そのジャンルに特化した検索を行う。
    """
    pk = f"USER#{user_id}"
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}

    # 残予算算出
    slack, total_budget = calculate_slack(user_id, ddb, profile)
    budget = int(slack)

    # 嗜好データ取得
    pref_memory = ddb.get_item(pk=pk, sk="PREF_MEMORY#") or {}

    # ジャンル指定がある場合: ホットペッパーで直接検索して1レーンで返す
    if genre and genre != "おまかせ":
        lanes = _build_genre_lanes(lat, lng, genre, budget, pref_memory)
    else:
        # 残予算に応じてレーン構成を決定
        if budget < 1000:
            lane_types = ["LOW_COST_RECOVERY", "CONVENIENCE_RECOVERY", "CAFE_REBOOT"]
        elif budget < 5000:
            lane_types = ["CAFE_REBOOT", "CONVENIENCE_RECOVERY", "SELF_COOKING_ESCAPE"]
        else:
            lane_types = ["CAFE_REBOOT", "SELF_COOKING_ESCAPE", "RICHER_ESCAPE"]

        lanes = []
        for lt in lane_types:
            places = search_nearby_places(lat, lng, lt)
            if not places:
                continue
            # ホットペッパーで店舗URL・画像・予算など詳細を補完
            places = _enrich_with_hotpepper(places, lat, lng, lt)
            definition = LANE_DEFINITIONS[lt]
            lane = {
                "lane_id": f"lane_{lt.lower()}_{uuid.uuid4().hex[:8]}",
                "lane_type": lt,
                "title": definition["title"],
                "estimated_min": definition["estimated_min"],
                "estimated_max": definition["estimated_max"],
                "ars_category": definition["ars_category"],
                "places": places[:3],
                "score": _calculate_score(lt, budget, pref_memory, places),
            }
            lanes.append(lane)

    # スコア順にソート
    lanes.sort(key=lambda x: x["score"], reverse=True)

    # 各レーンにご褒美提案を追加
    try:
        from services.reward_matcher import match_rewards_to_lane
        for lane in lanes:
            lane["rewards"] = match_rewards_to_lane(
                user_id=user_id,
                lane_type=lane["lane_type"],
                places=lane.get("places", []),
                budget_remaining=budget,
                ddb=ddb,
            )
    except Exception as e:
        logger.warning("reward_matching_failed", error=str(e))

    # Bedrock でおすすめ理由を生成
    reason = _generate_reason(message, lanes, budget)

    # ふれまーるちゃんによる各店舗の紹介文を生成
    try:
        _generate_place_descriptions(lanes)
    except Exception as e:
        logger.warning("place_descriptions_failed", error=str(e))

    # セッション保存
    session_id = uuid.uuid4().hex
    now = datetime.now(_JST).isoformat()
    session = {
        "session_id": session_id,
        "status": "proposed",
        "trigger_message": message,
        "created_at": now,
        "location": {"lat": str(lat), "lng": str(lng), "source": "liff_geolocation"},
        "lanes": lanes,
        "recommended_lane_id": lanes[0]["lane_id"] if lanes else None,
        "selected_lane_id": None,
    }
    # TTL: 30日
    ttl_epoch = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    session["ttl"] = ttl_epoch

    ddb.put_item(
        pk=pk,
        sk=f"TEMPTATION_SESSION#{session_id}",
        item=session,
    )

    return {
        "session_id": session_id,
        "lanes": lanes,
        "recommended_lane_id": lanes[0]["lane_id"] if lanes else None,
        "reason": reason,
        "budget_remaining": budget,
        "budget_total": int(total_budget),
    }


def accept_lane(user_id: str, session_id: str, lane_id: str, ddb: DynamoDBService) -> dict:
    """ユーザーがレーンを選択した時の処理。LINE Push でスポット詳細を送信する。"""
    pk = f"USER#{user_id}"
    sk = f"TEMPTATION_SESSION#{session_id}"

    # セッション取得してレーン情報を得る
    session = ddb.get_item(pk=pk, sk=sk) or {}
    selected_lane = None
    for lane in session.get("lanes", []):
        if lane.get("lane_id") == lane_id:
            selected_lane = lane
            break

    ddb.update_item(pk=pk, sk=sk, updates={
        "status": "accepted",
        "selected_lane_id": lane_id,
        "accepted_at": datetime.now(_JST).isoformat(),
    })

    return {"accepted": True, "lane_id": lane_id}


def try_complete_active_session(user_id: str, item_name: str, amount: int, ddb: DynamoDBService) -> str | None:
    """
    直近のacceptedセッションがあれば自動的にcomplete扱いにする。
    寄り道支出として紐付ける。成功時はお店名を返す。
    """
    pk = f"USER#{user_id}"
    sessions = ddb.query_by_pk(pk=pk, sk_prefix="TEMPTATION_SESSION#", descending=True, limit=5)

    # 直近のaccepted（未完了）セッションを探す
    active_session = None
    for s in sessions:
        if s.get("status") == "accepted":
            active_session = s
            break

    if not active_session:
        return None

    session_id = active_session.get("session_id", "")
    sk = active_session.get("SK") or active_session.get("sk") or f"TEMPTATION_SESSION#{session_id}"
    selected_lane_id = active_session.get("selected_lane_id", "")

    # 選択レーン情報
    selected_lane = None
    for lane in active_session.get("lanes", []):
        if lane.get("lane_id") == selected_lane_id:
            selected_lane = lane
            break

    place_name = ""
    if selected_lane and selected_lane.get("places"):
        place_name = selected_lane["places"][0].get("name", "")

    # セッション完了に更新
    now = datetime.now(_JST)
    ddb.update_item(pk=pk, sk=sk, updates={
        "status": "completed",
        "completed_at": now.isoformat(),
    })

    return place_name or selected_lane.get("title", "") if selected_lane else None


def complete_temptation(
    user_id: str,
    session_id: str,
    lane_id: str,
    amount: int,
    item_name: str,
    place_name: str,
    reward_id: str | None,
    ddb: DynamoDBService,
) -> dict:
    """寄り道完了 → 支出記録を自動生成し、セッションを完了にする。"""
    pk = f"USER#{user_id}"
    sk = f"TEMPTATION_SESSION#{session_id}"

    session = ddb.get_item(pk=pk, sk=sk) or {}
    if not session:
        return {"error": "session_not_found"}

    # 選択されたレーン情報を取得
    selected_lane = None
    for lane in session.get("lanes", []):
        if lane.get("lane_id") == lane_id:
            selected_lane = lane
            break

    ars_category = selected_lane.get("ars_category", "回復費") if selected_lane else "回復費"

    # EXPENSE レコード生成
    now = datetime.now(_JST)
    expense_id = uuid.uuid4().hex
    expense_sk = f"EXPENSE#{now.strftime('%Y-%m-%d')}#{expense_id}"

    expense_item = {
        "amount": amount,
        "category": ars_category,
        "item_name": item_name,
        "date": now.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "temptation_session_id": session_id,
        "lane_type": selected_lane.get("lane_type", "") if selected_lane else "",
        "place_name": place_name,
        "location_based": True,
        "entityType": "EXPENSE",
    }
    if reward_id:
        expense_item["reward_id"] = reward_id

    ttl_epoch = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
    expense_item["ttl"] = ttl_epoch

    ddb.put_item(pk=pk, sk=expense_sk, item=expense_item)

    # セッション完了に更新
    ddb.update_item(pk=pk, sk=sk, updates={
        "status": "completed",
        "completed_at": now.isoformat(),
        "completed_expense_id": expense_id,
    })

    # 残予算を再計算
    from services.finance_engine import calculate_slack
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    slack, _ = calculate_slack(user_id, ddb, profile)

    # ふれまーるちゃんの完了メッセージ生成
    message = _generate_complete_message(item_name, amount, ars_category, int(slack))

    return {
        "expense_id": expense_id,
        "budget_remaining": int(slack),
        "message": message,
    }


def _generate_complete_message(item_name: str, amount: int, category: str, remaining: int) -> str:
    """ワンタップ完了時のふれまーるちゃんメッセージ。"""
    try:
        prompt = (
            f"あなたはふれまーるちゃん（ゆるふわ森ガールのアシスタント、🌿がトレードマーク）です。\n"
            f"ユーザーが寄り道で「{item_name}」を{amount}円で買いました。\n"
            f"カテゴリは「{category}」で、今月の残り予算は{remaining}円です。\n\n"
            f"1〜2文で、購入を優しく認めつつ残予算を伝えるメッセージを書いてください。\n"
            f"語尾は「〜だよ〜」「〜だね」等。絵文字を🌿など自然系で2個使ってください。"
        )
        return _bedrock.invoke_text(prompt, max_tokens=150, temperature=0.8)
    except Exception:
        return f"{item_name}、おつかれさま～🌿 今月の{category}はあと{remaining:,}円だよ🌿"


def get_temptation_history(user_id: str, ddb: DynamoDBService) -> dict:
    """今月の寄り道セッション履歴を集計する。"""
    pk = f"USER#{user_id}"
    now = datetime.now(_JST)
    month_prefix = now.strftime("%Y-%m")

    sessions = ddb.query_by_pk(pk=pk, sk_prefix="TEMPTATION_SESSION#", descending=True)

    # 今月のセッションをフィルタ（proposed=提案済み, accepted=行く予定, completed=完了）
    this_month_sessions = sorted(
        [
            s for s in sessions
            if s.get("created_at", "").startswith(month_prefix)
            and s.get("status") in ("proposed", "accepted", "completed")
        ],
        key=lambda s: s.get("created_at", ""),
        reverse=True,  # 最新を先頭に
    )

    by_lane: dict[str, dict] = {}
    frequent_places: dict[str, int] = {}

    # セッション一覧（LIFF表示用）
    recent_sessions: list[dict] = []

    for s in this_month_sessions:
        # proposed は recommended_lane_id、accepted/completed は selected_lane_id を使う
        selected = s.get("selected_lane_id", "") or s.get("recommended_lane_id", "")
        session_info: dict = {
            "session_id": s.get("session_id", "") or s.get("sk", "").replace("TEMPTATION_SESSION#", ""),
            "status": s.get("status", ""),
            "created_at": s.get("created_at", ""),
            "accepted_at": s.get("accepted_at", ""),
            "lane_title": "",
            "places": [],
            "expense_recorded": s.get("status") == "completed",
        }

        for lane in s.get("lanes", []):
            if lane.get("lane_id") == selected:
                lt = lane.get("lane_type", "UNKNOWN")
                # by_lane 統計は accepted/completed のみ
                if s.get("status") in ("accepted", "completed"):
                    if lt not in by_lane:
                        by_lane[lt] = {"count": 0, "total": 0}
                    by_lane[lt]["count"] += 1
                    by_lane[lt]["total"] += lane.get("estimated_max", 0)

                session_info["lane_title"] = lane.get("title", "")
                session_info["lane_type"] = lt
                session_info["places"] = [
                    {
                        "name": p.get("name", ""),
                        "genre": p.get("genre", p.get("category", "")),
                        "shop_url": p.get("shop_url", ""),
                        "image_url": p.get("image_url", ""),
                        "distance_m": p.get("distance_m", 0),
                        "lat": p.get("lat", ""),
                        "lng": p.get("lng", ""),
                        "budget_text": p.get("budget_text", ""),
                        "description": p.get("description", ""),
                    }
                    for p in lane.get("places", [])[:3]
                ]

                # 頻出スポット
                for p in lane.get("places", [])[:1]:
                    name = p.get("name", "")
                    if name:
                        frequent_places[name] = frequent_places.get(name, 0) + 1
                break

        recent_sessions.append(session_info)

    # 頻出スポット上位3件
    top_places = sorted(frequent_places.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "this_month": {
            "total_detours": len(this_month_sessions),
            "by_lane": by_lane,
            "frequent_places": [p[0] for p in top_places],
        },
        "recent_sessions": recent_sessions[:10],
    }


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────
def _build_genre_lanes(lat: float, lng: float, genre: str, budget: int, pref_memory: dict) -> list[dict]:
    """ジャンル指定時: ホットペッパーで直接検索して結果を1レーンとして返す。"""
    from services.hotpepper_service import search_nearby_restaurants

    keyword = _GENRE_TO_KEYWORD.get(genre, genre)
    if not keyword:
        keyword = genre

    try:
        hp_results = search_nearby_restaurants(lat=lat, lng=lng, keyword=keyword, range_code=3, count=10)
    except Exception as e:
        logger.warning("genre_search_hotpepper_failed", error=str(e))
        hp_results = []

    if not hp_results:
        # ホットペッパーで見つからない場合は Overpass でフォールバック
        places = search_nearby_places(lat, lng, "CAFE_REBOOT")
        places = _enrich_with_hotpepper(places, lat, lng, "CAFE_REBOOT")
    else:
        places = []
        for r in hp_results[:5]:
            dist = _haversine(lat, lng, float(r.lat), float(r.lng)) if r.lat and r.lng else 500
            places.append({
                "name": r.name,
                "genre": r.genre_name,
                "shop_url": r.shop_url,
                "image_url": r.image_url,
                "distance_m": int(dist),
                "lat": str(r.lat),
                "lng": str(r.lng),
                "budget_text": f"¥{r.price}" if r.price else "",
                "category": r.genre_name,
            })

    # ジャンルに合ったレーンタイプを推定
    genre_lane_map = {
        "カフェ": "CAFE_REBOOT",
        "スイーツ": "CAFE_REBOOT",
        "ラーメン": "SELF_COOKING_ESCAPE",
        "定食": "SELF_COOKING_ESCAPE",
        "パン": "CAFE_REBOOT",
        "居酒屋": "RICHER_ESCAPE",
        "コンビニ": "CONVENIENCE_RECOVERY",
    }
    lt = genre_lane_map.get(genre, "SELF_COOKING_ESCAPE")
    definition = LANE_DEFINITIONS[lt]

    lane = {
        "lane_id": f"lane_genre_{uuid.uuid4().hex[:8]}",
        "lane_type": lt,
        "title": f"{genre}で寄り道 🌿",
        "estimated_min": definition["estimated_min"],
        "estimated_max": definition["estimated_max"],
        "ars_category": definition["ars_category"],
        "places": places[:3],
        "score": 90,  # ジャンル指定は高スコア
    }
    return [lane]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の距離(m)を計算。"""
    import math
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _calculate_score(lane_type: str, budget: int, pref_memory: dict, places: list) -> int:
    """レーンのスコアを計算。嗜好・距離・予算を考慮。"""
    base = 50

    # 距離スコア
    if places:
        avg_distance = sum(p.get("distance_m", 500) for p in places) / len(places)
        if avg_distance < 200:
            base += 20
        elif avg_distance < 500:
            base += 10

    # 予算適合スコア
    definition = LANE_DEFINITIONS[lane_type]
    if definition["estimated_max"] <= budget * 0.1:
        base += 15

    # 嗜好データでブースト（food.likes + categories 両方を参照）
    food_likes = pref_memory.get("food", {}).get("likes", []) if isinstance(pref_memory.get("food"), dict) else []
    categories = pref_memory.get("categories", [])
    all_prefs = [str(x).lower() for x in food_likes + categories]

    if lane_type == "SELF_COOKING_ESCAPE" and any(k in " ".join(all_prefs) for k in ["ラーメン", "定食", "カレー", "中華", "グルメ"]):
        base += 20
    if lane_type == "CAFE_REBOOT" and any(k in " ".join(all_prefs) for k in ["カフェ", "コーヒー", "紅茶", "抹茶", "スイーツ"]):
        base += 15
    if lane_type == "RICHER_ESCAPE" and any(k in " ".join(all_prefs) for k in ["イタリアン", "フレンチ", "焼肉", "寿司", "ダイニング"]):
        base += 15

    return min(base, 100)


def _generate_reason(message: str, lanes: list, budget: int) -> str:
    """Bedrock でふれまーるちゃんのおすすめ理由を生成。"""
    if not lanes:
        return "近くにいい場所が見つからなかった…ごめんね🌿"

    top_lane = lanes[0]
    top_place = top_lane["places"][0] if top_lane.get("places") else None
    place_info = f"近くに{top_place['name']}があるよ（徒歩{top_place['distance_m'] // 80}分）" if top_place else ""

    prompt = (
        f"あなたはふれまーるちゃん（ゆるふわ森ガールのアシスタント、🌿がトレードマーク）です。\n"
        f"ユーザーが「{message}」と言っています。\n"
        f"残予算は{budget}円です。\n"
        f"おすすめの寄り道レーンは「{top_lane['title']}」で、{place_info}。\n"
        f"想定金額は{top_lane['estimated_min']}〜{top_lane['estimated_max']}円です。\n\n"
        f"2〜3文で、このレーンをおすすめする理由をふれまーるちゃんの口調で書いてください。\n"
        f"語尾は「〜だよ〜」「〜しよ？」等。絵文字を🌿🌸🌱など2〜3個使い、「甘やかし」「癒し」という言葉を自然に入れてください。"
    )

    try:
        return _bedrock.invoke_text(prompt, max_tokens=200, temperature=0.8)
    except Exception as e:
        logger.warning("temptation_reason_generation_failed", error=str(e))
        return f"今日の甘やかしは{top_lane['title']}で決まり～🌿 予算的にも全然いけるよ🌸"


def _generate_place_descriptions(lanes: list) -> None:
    """各レーンのplacesにふれまーるちゃんの紹介文を付与する（in-place）。"""
    places_to_describe = []
    for lane in lanes:
        for p in lane.get("places", [])[:3]:
            places_to_describe.append(p)

    if not places_to_describe:
        return

    # バッチで一度にBedrock呼び出し
    place_list_text = "\n".join(
        f"- {p.get('name','?')}（{p.get('genre', p.get('category', ''))}, "
        f"徒歩{max(1, p.get('distance_m',0)//80)}分"
        f"{', 予算' + p.get('budget_text','') if p.get('budget_text') else ''}）"
        for p in places_to_describe
    )

    prompt = (
        "あなたはふれまーるちゃん（🌿ゆるふわ森ガールのアシスタント）です。\n"
        "以下のお店リストについて、各店艗1行（30文字以内）で魅力を紹介してください。\n"
        "ふれまーるちゃんの口調（ゆるふわで優しい、「〜だよ〜」「〜かも〜」）で書いてね。\n"
        "各行は「店名: 紹介文」の形式で出力してください。\n\n"
        f"{place_list_text}"
    )

    try:
        result = _bedrock.invoke_text(prompt, max_tokens=400, temperature=0.7)
        # パース: 各行を店名ごとに割り当て
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
        for i, p in enumerate(places_to_describe):
            if i < len(lines):
                # "店名: 紹介文" or "- 店名: 紹介文" 形式をパース
                line = lines[i].lstrip("- ").lstrip("・")
                if ":" in line:
                    p["description"] = line.split(":", 1)[1].strip()
                elif "：" in line:
                    p["description"] = line.split("：", 1)[1].strip()
                else:
                    p["description"] = line
            else:
                p["description"] = ""
    except Exception as e:
        logger.warning("place_description_generation_failed", error=str(e))


def _enrich_with_hotpepper(places: list[dict], lat: float, lng: float, lane_type: str) -> list[dict]:
    """Overpass で見つけた場所をホットペッパーで補完し、URL/画像/予算を付与する。"""
    keyword = _LANE_TYPE_KEYWORDS.get(lane_type, "")
    if not keyword:
        # コンビニ等はホットペッパーに載っていないのでスキップ
        return places

    try:
        from services.hotpepper_service import search_nearby_restaurants, HotPepperAPIError
        hp_results = search_nearby_restaurants(
            lat=lat, lng=lng, keyword=keyword, range_code=3, count=10,
        )
    except Exception as e:
        logger.warning("hotpepper_enrich_failed", error=str(e))
        return places

    if not hp_results:
        return places

    # ホットペッパー結果を名前で引ける辞書にする
    hp_by_name: dict[str, object] = {}
    for r in hp_results:
        hp_by_name[r.name] = r

    enriched = []
    matched_hp_ids: set[str] = set()

    for place in places:
        name = place.get("name", "")
        matched = hp_by_name.get(name)
        if not matched:
            # 部分一致を試みる
            for hp in hp_results:
                if hp.shop_id in matched_hp_ids:
                    continue
                if name in hp.name or hp.name in name:
                    matched = hp
                    break

        if matched:
            matched_hp_ids.add(matched.shop_id)
            place["shop_url"] = matched.shop_url
            place["image_url"] = matched.image_url or ""
            place["genre"] = matched.genre_name
            place["budget_text"] = f"¥{matched.price}" if matched.price else ""
            place["station"] = matched.station_name
        enriched.append(place)

    # Overpass にマッチしなかったホットペッパー店舗を追加（上位分まで）
    for hp in hp_results:
        if hp.shop_id not in matched_hp_ids and len(enriched) < 5:
            enriched.append({
                "name": hp.name,
                "category": hp.genre_name,
                "lat": lat,
                "lng": lng,
                "address": hp.station_name,
                "distance_m": 0,
                "shop_url": hp.shop_url,
                "image_url": hp.image_url or "",
                "genre": hp.genre_name,
                "budget_text": f"¥{hp.price}" if hp.price else "",
                "station": hp.station_name,
            })

    return enriched
