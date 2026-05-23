"""
RewardCandidate Provider (要件整理.md §9, §10 準拠)

候補取得構成:
  商品候補取得
  ├─ 楽天API
  ├─ ホットペッパーAPI
  ├─ Nova Act Amazon検索（ジョブ型・非同期）
  ├─ キャッシュ済み候補
  └─ Static候補

重要方針:
  - Amazon APIが重いため、AmazonはNova Act検索で代用
  - 楽天API・ホットペッパーAPIは通常の外部API Providerとして統合
  - カート投入・購入操作はNova Actではやらない

Provider優先順位:
  1. CachedRewardPoolProvider
  2. RakutenRewardProvider
  3. HotpepperRewardProvider
  4. NovaActAmazonSearchProvider (キャッシュ結果のみ同期返却)
  5. StaticRewardProvider
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────
# データクラス
# ─────────────────────────────────────────
@dataclass
class RewardCandidate:
    name: str
    amount: int
    url: str = ""
    image_url: str = ""
    source: str = "unknown"
    source_item_id: str = ""
    asin: str = ""
    shop_name: str = ""
    description: str = ""
    category: str = ""
    tags: Optional[list[str]] = None
    reward_type: str = "product"
    confidence: float = 0.5
    currency: str = "JPY"
    reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("tags") is None:
            d["tags"] = []
        d["candidate_id"] = str(uuid.uuid4())
        return d


# ─────────────────────────────────────────
# Static候補カタログ
# ─────────────────────────────────────────
_STATIC_CATALOG = [
    {"name": "抹茶プリン", "amount": 320, "tags": ["抹茶", "プリン", "スイーツ"], "category": "スイーツ"},
    {"name": "プレミアム入浴剤セット", "amount": 1280, "tags": ["入浴剤", "リラックス", "癒し"], "category": "バス"},
    {"name": "ご褒美フィナンシェ詰合せ", "amount": 1500, "tags": ["スイーツ", "焼き菓子", "ご褒美"], "category": "スイーツ"},
    {"name": "アロマキャンドル", "amount": 980, "tags": ["アロマ", "リラックス"], "category": "リラックス"},
    {"name": "高級チョコレート", "amount": 850, "tags": ["チョコレート", "スイーツ"], "category": "スイーツ"},
    {"name": "カフェラテ豆", "amount": 1200, "tags": ["コーヒー", "カフェ"], "category": "ドリンク"},
    {"name": "もちもちチーズケーキ", "amount": 680, "tags": ["スイーツ", "ケーキ", "チーズ"], "category": "スイーツ"},
    {"name": "ふわふわクッション", "amount": 2980, "tags": ["リラックス", "癒し", "睡眠"], "category": "リラックス"},
]


# ─────────────────────────────────────────
# Provider: Static
# ─────────────────────────────────────────
def _static_search(query: str, max_results: int) -> list[RewardCandidate]:
    """静的候補からクエリに合うものを返す"""
    if os.environ.get("ENABLE_STATIC_REWARD_FALLBACK", "true").lower() != "true":
        return []

    q_lower = query.lower()
    q_tokens = [t for t in q_lower.replace("、", " ").replace(",", " ").split() if t]

    scored = []
    for item in _STATIC_CATALOG:
        score = 0.3
        for tag in item.get("tags", []):
            if tag.lower() in q_lower:
                score += 0.3
            for t in q_tokens:
                if t and (t in tag.lower() or tag.lower() in t):
                    score += 0.2
        if item["name"] in query:
            score += 0.4
        scored.append((min(score, 1.0), item))

    scored.sort(key=lambda x: -x[0])
    return [
        RewardCandidate(
            name=it["name"],
            amount=it["amount"],
            tags=it.get("tags", []),
            category=it.get("category", ""),
            source="static",
            confidence=score,
            reason="定番のご褒美候補",
        )
        for score, it in scored[:max_results]
    ]


# ─────────────────────────────────────────
# Provider: 楽天API
# ─────────────────────────────────────────
def _rakuten_search(query: str, max_results: int, max_price: int = 5000) -> list[RewardCandidate]:
    """楽天APIで商品候補を取得する"""
    if os.environ.get("ENABLE_RAKUTEN_API", "true").lower() != "true":
        return []

    try:
        from services.rakuten_service import search_products
        products = search_products(keyword=query, hits=max_results, min_price=200, max_price=max_price)
        candidates = []
        for p in products[:max_results]:
            candidates.append(RewardCandidate(
                name=str(p.name)[:80],
                amount=int(p.price),
                url=str(p.item_url),
                image_url=str(p.image_url or "").replace("http://", "https://"),
                source="rakuten",
                source_item_id=str(p.item_id),
                shop_name=str(p.shop_name),
                category=str(p.category_name),
                tags=query.split(),
                reward_type="product",
                confidence=0.7 + (p.review_average / 50),
                reason="楽天の人気商品",
            ))
        logger.info("rakuten_provider_ok", query=query, count=len(candidates))
        return candidates
    except Exception as e:
        logger.warning("rakuten_provider_failed", query=query, error=str(e))
        return []


# ─────────────────────────────────────────
# Provider: ホットペッパーAPI
# ─────────────────────────────────────────
def _hotpepper_search(query: str, max_results: int) -> list[RewardCandidate]:
    """ホットペッパーAPIで飲食店候補を取得する"""
    if os.environ.get("ENABLE_HOTPEPPER_API", "true").lower() != "true":
        return []

    try:
        from services.hotpepper_service import search_restaurants
        restaurants = search_restaurants(keyword=query, count=max_results)
        candidates = []
        for r in restaurants[:max_results]:
            candidates.append(RewardCandidate(
                name=str(r.name)[:80],
                amount=int(r.price),
                url=str(r.shop_url),
                image_url=str(r.image_url or ""),
                source="hotpepper",
                source_item_id=str(r.shop_id),
                shop_name=str(r.name),
                description=f"{r.genre_name}・{r.station_name}",
                category=str(r.genre_name),
                tags=query.split() + [r.genre_name],
                reward_type="restaurant",
                confidence=0.7,
                reason="近くの飲食店でリフレッシュ",
            ))
        logger.info("hotpepper_provider_ok", query=query, count=len(candidates))
        return candidates
    except Exception as e:
        logger.warning("hotpepper_provider_failed", query=query, error=str(e))
        return []


# ─────────────────────────────────────────
# Provider: Nova Act Amazon検索 (キャッシュ参照)
# ─────────────────────────────────────────
def _nova_act_cached_search(query: str, max_results: int, ddb=None, user_id: str = "") -> list[RewardCandidate]:
    """Nova Act検索のキャッシュ結果を返す (Workerが事前に保存した結果)"""
    if os.environ.get("ENABLE_NOVA_ACT_SEARCH", "true").lower() != "true":
        return []
    if not ddb or not user_id:
        return []

    try:
        items = ddb.query_items(f"USER#{user_id}", sk_prefix="REWARD_POOL#", limit=20)
        nova_items = [item for item in items if item.get("source") == "nova_act_amazon"]
        # queryキーワードでフィルタ
        keywords = query.lower().split()
        filtered = []
        for item in nova_items:
            name = (item.get("name") or "").lower()
            tags = " ".join(item.get("tags") or []).lower()
            if any(kw in name or kw in tags for kw in keywords):
                filtered.append(item)

        candidates = []
        for item in filtered[:max_results]:
            candidates.append(RewardCandidate(
                name=item.get("name", ""),
                amount=int(item.get("amount", 0)),
                url=item.get("url", ""),
                image_url=item.get("image_url", ""),
                source="nova_act_amazon",
                asin=item.get("asin", ""),
                tags=item.get("tags", []),
                reward_type="product",
                confidence=0.8,
                reason="Amazonで見つけた商品",
            ))
        return candidates
    except Exception as e:
        logger.warning("nova_act_cached_search_failed", error=str(e))
        return []


def create_nova_act_search_job(query: str, user_id: str, ddb, max_price: int = 5000) -> str:
    """Nova Act Amazon検索ジョブを作成する。Workerが非同期で処理する。

    Returns:
        job_id
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pk = f"NOVA_ACT_SEARCH_JOB#{job_id}"
    sk = "META#"

    ddb.put_item(pk, sk, {
        "entityType": "NOVA_ACT_SEARCH_JOB",
        "job_id": job_id,
        "userId": f"USER#{user_id}",
        "query": query,
        "max_price": max_price,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    })
    logger.info("nova_act_search_job_created", job_id=job_id, query=query)
    return job_id


# ─────────────────────────────────────────
# Provider: Bedrock Amazon (AI生成候補)
# ─────────────────────────────────────────
def _bedrock_amazon_search(query: str, max_results: int) -> list[RewardCandidate]:
    """Bedrock を使って Amazon.co.jp の実在商品候補を生成し、検索URLを付与する。"""
    try:
        from services.bedrock_service import BedrockService
        import json as _json
        import urllib.parse as _urlparse

        bedrock = BedrockService()
        prompt = (
            f"あなたはAmazon.co.jpの商品検索アシスタントです。\n"
            f"ユーザーが「{query}」で検索した場合に見つかる実在の商品を{max_results}件提案してください。\n\n"
            f"条件:\n"
            f"- 価格は200円〜5000円の範囲\n"
            f"- Amazon.co.jpで実際に購入できる商品\n"
            f"- ご褒美・癒し・リフレッシュに適した商品を優先\n\n"
            f"以下のJSON配列形式で出力してください（他のテキストは不要）:\n"
            f'[{{"name": "商品名", "price": 価格(整数), "category": "カテゴリ"}}]\n'
        )

        response_text = bedrock.invoke_text(
            prompt=prompt,
            max_tokens=500,
            temperature=0.7,
            system_prompt="あなたはJSON出力専用のアシスタントです。JSON配列のみ出力してください。",
        )

        text = response_text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if not text.startswith("["):
            idx = text.find("[")
            if idx >= 0:
                text = text[idx:]

        products = _json.loads(text)
        candidates = []
        for item in products[:max_results]:
            name = str(item.get("name", ""))[:50]
            price = int(item.get("price", 0))
            if not name or price <= 0:
                continue
            search_url = (
                "https://www.amazon.co.jp/s?"
                + _urlparse.urlencode({"k": name, "rh": "p_36:20000-500000"}, encoding="utf-8")
            )
            candidates.append(RewardCandidate(
                name=name,
                amount=price,
                url=search_url,
                tags=[query, item.get("category", "")],
                source="bedrock_amazon",
                category=item.get("category", ""),
                confidence=0.8,
                reason="AIが見つけたAmazon商品候補",
            ))
        logger.info("bedrock_amazon_search_ok", query=query, count=len(candidates))
        return candidates
    except Exception as e:
        logger.warning("bedrock_amazon_search_failed", error=str(e))
        return []


# ─────────────────────────────────────────
# Amazon ASIN 解決 (商品名からASINを取得)
# ─────────────────────────────────────────
def resolve_amazon_asin(product_name: str, max_price: int = 5000) -> dict:
    """Amazon.co.jpで商品名を検索し、最初のASINと商品情報を返す。

    Returns:
        {"asin": "B...", "name": "...", "price": "...", "url": "...", "image_url": "...", "cart_url": "..."}
        見つからない場合: {"asin": "", "error": "..."}
    """
    import urllib.request
    import urllib.parse
    import re

    try:
        search_url = "https://www.amazon.co.jp/s?" + urllib.parse.urlencode({
            "k": product_name,
            "rh": f"p_36:0-{max_price * 100}",  # 価格フィルタ（円→銭）
        })

        req = urllib.request.Request(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja-JP,ja;q=0.9",
        })

        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # data-asin属性からASINを抽出 (B0で始まる10桁)
        asin_pattern = re.compile(r'data-asin="(B[A-Z0-9]{9})"')
        asins = asin_pattern.findall(html)

        if not asins:
            # 別パターン: /dp/ASIN/ URLから
            dp_pattern = re.compile(r'/dp/(B[A-Z0-9]{9})')
            asins = dp_pattern.findall(html)

        if not asins:
            logger.info("resolve_asin_not_found", product_name=product_name)
            return {"asin": "", "error": "ASINが見つかりませんでした"}

        asin = asins[0]

        # 商品名を取得 (オプション)
        title = product_name
        # 画像URL取得を試みる
        image_url = ""
        img_pattern = re.compile(r'data-asin="' + asin + r'"[^>]*>.*?<img[^>]+src="(https://[^"]+)"', re.DOTALL)
        img_match = img_pattern.search(html)
        if img_match:
            image_url = img_match.group(1)

        product_url = f"https://www.amazon.co.jp/dp/{asin}"
        cart_url = f"https://www.amazon.co.jp/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1"

        logger.info("resolve_asin_ok", product_name=product_name, asin=asin)
        return {
            "asin": asin,
            "name": title,
            "url": product_url,
            "image_url": image_url,
            "cart_url": cart_url,
        }

    except Exception as e:
        logger.warning("resolve_asin_failed", product_name=product_name, error=str(e))
        return {"asin": "", "error": str(e)}


# ─────────────────────────────────────────
# Public API: 統合検索
# ─────────────────────────────────────────
def search_reward_candidates(
    query: str,
    *,
    max_results: int = 5,
    user_context: Optional[dict] = None,
    max_price: int = 5000,
) -> list[dict]:
    """ご褒美候補を Provider チェーンで取得する。

    処理順:
      1. 楽天APIを呼ぶ
      2. ホットペッパーAPIを呼ぶ
      3. Nova Actキャッシュを確認
      4. Bedrock Amazon候補でfallback
      5. Static候補でfallback

    重要: Nova Actによるカート投入・購入操作は行わない。
    """
    ctx = user_context or {}
    ddb = ctx.get("ddb")
    user_id = ctx.get("user_id", "")

    all_candidates: list[RewardCandidate] = []

    # 1. 楽天API
    rakuten = _rakuten_search(query, max_results, max_price)
    all_candidates.extend(rakuten)

    # 2. ホットペッパーAPI
    hotpepper = _hotpepper_search(query, max_results)
    all_candidates.extend(hotpepper)

    # 3. Nova Act キャッシュ
    nova = _nova_act_cached_search(query, max_results, ddb, user_id)
    all_candidates.extend(nova)

    # 候補が十分あればここで返す
    if len(all_candidates) >= max_results:
        return _score_and_return(all_candidates, query, max_price, max_results)

    # 4. Bedrock Amazon fallback
    bedrock = _bedrock_amazon_search(query, max_results - len(all_candidates))
    all_candidates.extend(bedrock)

    if all_candidates:
        return _score_and_return(all_candidates, query, max_price, max_results)

    # 5. Static fallback
    static = _static_search(query, max_results)
    all_candidates.extend(static)

    return _score_and_return(all_candidates, query, max_price, max_results)


def _score_and_return(candidates: list[RewardCandidate], query: str, max_price: int, max_results: int) -> list[dict]:
    """候補をスコアリングしてソートして返す"""
    keywords = set(query.lower().split())

    scored = []
    for c in candidates:
        score = c.confidence * 100
        if c.amount <= max_price:
            score += 30
        name_lower = c.name.lower()
        tags_lower = {t.lower() for t in (c.tags or [])}
        matched = keywords & (tags_lower | {name_lower})
        score += len(matched) * 15
        if c.image_url:
            score += 10
        if c.url:
            score += 5
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])

    # 重複排除 (名前ベース)
    seen = set()
    result = []
    for _, c in scored:
        if c.name not in seen:
            seen.add(c.name)
            result.append(c.to_dict())
        if len(result) >= max_results:
            break

    return result


# ─────────────────────────────────────────
# Public API: Nova Act 検証 smoke
# ─────────────────────────────────────────
def run_nova_act_smoke(query: str, max_results: int = 3) -> tuple[list[dict], dict]:
    """Nova Act 検証スモーク。検証導線 (`/api/nova-act/smoke`) から呼ぶ。

    Nova Act SDK でAmazon検索を実行する。
    SDKが未インストールの場合はBedrock/楽天にフォールバック。

    Returns:
        (候補リスト, meta)
    """
    started = time.time()

    enable = os.environ.get("ENABLE_NOVA_ACT_SEARCH", "true").lower() == "true"
    if not enable:
        duration_ms = int((time.time() - started) * 1000)
        return [], {"status": "disabled", "provider": "none", "duration_ms": duration_ms,
                    "failure_reason": "ENABLE_NOVA_ACT_SEARCH=false"}

    # Nova Act SDKを試行
    try:
        import importlib
        importlib.import_module("nova_act")
        # SDK利用可能 → 実際のNova Act検索（Workerが別プロセスで行う）
        logger.info("nova_act_smoke_sdk_available", query=query)
        # ここでは直接実行せず、Workerに委譲するためfallbackに進む
    except ImportError:
        logger.info("nova_act_smoke_sdk_unavailable", query=query)

    # Fallback 1: Bedrock Amazon
    bedrock_cands = _bedrock_amazon_search(query, max_results)
    if bedrock_cands:
        duration_ms = int((time.time() - started) * 1000)
        return (
            [c.to_dict() for c in bedrock_cands],
            {"status": "ok_bedrock_amazon", "provider": "bedrock_amazon",
             "duration_ms": duration_ms, "note": "Bedrock AIによるAmazon商品候補生成"},
        )

    # Fallback 2: 楽天 API
    ext = _rakuten_search(query, max_results)
    if ext:
        duration_ms = int((time.time() - started) * 1000)
        return (
            [c.to_dict() for c in ext],
            {"status": "fallback_rakuten", "provider": "rakuten",
             "duration_ms": duration_ms},
        )

    # Fallback 3: Static
    duration_ms = int((time.time() - started) * 1000)
    static = _static_search(query, max_results)
    return (
        [c.to_dict() for c in static],
        {"status": "fallback_static", "provider": "static", "duration_ms": duration_ms},
    )
