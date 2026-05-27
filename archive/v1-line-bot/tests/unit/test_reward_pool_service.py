"""
reward_pool_service ユニットテスト
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import PrefItem, PrefMemory, RewardPoolItem, SK_PREFIX_REWARD_POOL
from services.rakuten_service import RakutenHotel, RakutenProduct
from services.reward_pool_service import (
    _clamp,
    _calc_base_score,
    _calc_review_bonus,
    _calc_base_score_text,
    _calc_review_bonus_generic,
    adjust_score,
    apply_type_weights,
    build_keywords,
    merge_pool,
    score_hotels,
    score_items,
    score_restaurants,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def _make_product(
    item_id: str = "item001",
    name: str = "スイーツセット",
    price: int = 980,
    category: str = "スイーツ",
    review_avg: float = 4.5,
    review_count: int = 100,
) -> RakutenProduct:
    return RakutenProduct(
        item_id=item_id,
        name=name,
        price=Decimal(str(price)),
        category_name=category,
        item_url=f"https://example.com/{item_id}",
        image_url=None,
        shop_name="TestShop",
        review_average=review_avg,
        review_count=review_count,
    )


def _make_pool_item(
    item_id: str = "item001",
    name: str = "スイーツ",
    score: float = 0.5,
    item_type: str = "product",
) -> RewardPoolItem:
    return RewardPoolItem(
        id=item_id,
        name=name,
        price=Decimal("980"),
        category="スイーツ",
        score=score,
        type=item_type,
    )


# ─────────────────────────────────────────
# _clamp テスト
# ─────────────────────────────────────────
class TestClamp:
    def test_範囲内はそのまま(self):
        assert _clamp(0.5) == 0.5

    def test_上限超過は1に(self):
        assert _clamp(1.5) == 1.0

    def test_下限未満は0に(self):
        assert _clamp(-0.1) == 0.0

    def test_境界値0(self):
        assert _clamp(0.0) == 0.0

    def test_境界値1(self):
        assert _clamp(1.0) == 1.0


# ─────────────────────────────────────────
# build_keywords テスト
# ─────────────────────────────────────────
class TestBuildKeywords:
    def test_嗜好なし_デフォルトを返す(self):
        result = build_keywords(None, ["スイーツ", "コスメ"])
        assert result == ["スイーツ", "コスメ"]

    def test_categories優先(self):
        pref = PrefMemory(
            pk="USER#test",
            categories=["スイーツ", "コスメ", "本"],
            items=[],
        )
        result = build_keywords(pref, [])
        # categories から最大2件
        assert "スイーツ" in result
        assert "コスメ" in result
        assert len(result) <= 5

    def test_positiveアイテムが含まれる(self):
        pref = PrefMemory(
            pk="USER#test",
            categories=[],
            items=[
                PrefItem(keyword="チョコレート", category="スイーツ", sentiment="positive", detected_at="2026-05-16"),
                PrefItem(keyword="嫌いなもの", category="食品", sentiment="negative", detected_at="2026-05-16"),
            ],
        )
        result = build_keywords(pref, [])
        assert "チョコレート" in result
        assert "嫌いなもの" not in result

    def test_重複排除(self):
        pref = PrefMemory(
            pk="USER#test",
            categories=["スイーツ"],
            items=[PrefItem(keyword="スイーツ", category="食品", sentiment="positive", detected_at="2026-05-16")],
        )
        result = build_keywords(pref, [])
        assert result.count("スイーツ") == 1

    def test_上限5件(self):
        pref = PrefMemory(
            pk="USER#test",
            categories=["A", "B"],
            items=[
                PrefItem(keyword="C", category="x", sentiment="positive", detected_at="2026-05-16"),
                PrefItem(keyword="D", category="x", sentiment="positive", detected_at="2026-05-16"),
                PrefItem(keyword="E", category="x", sentiment="positive", detected_at="2026-05-16"),
                PrefItem(keyword="F", category="x", sentiment="positive", detected_at="2026-05-16"),
            ],
        )
        result = build_keywords(pref, [])
        assert len(result) <= 5

    def test_空嗜好_デフォルトを使用(self):
        pref = PrefMemory(pk="USER#test", categories=[], items=[])
        result = build_keywords(pref, ["入浴剤"])
        assert result == ["入浴剤"]


# ─────────────────────────────────────────
# score_items テスト
# ─────────────────────────────────────────
class TestScoreItems:
    def test_スコアは0以上1以下(self):
        products = [_make_product(), _make_product(item_id="002", name="コスメセット", category="コスメ")]
        items = score_items(products, ["スイーツ", "コスメ"])
        for item in items:
            assert 0.0 <= item.score <= 1.0

    def test_スコア降順ソート(self):
        # スイーツ関連が上位に来るはず
        products = [
            _make_product(item_id="001", name="スイーツセット", category="スイーツ", review_avg=4.5, review_count=100),
            _make_product(item_id="002", name="全然関係ない商品", category="ガジェット", review_avg=2.0, review_count=5),
        ]
        items = score_items(products, ["スイーツ"])
        assert items[0].id == "001"

    def test_空商品リスト(self):
        items = score_items([], ["スイーツ"])
        assert items == []

    def test_RewardPoolItemに変換される(self):
        products = [_make_product()]
        items = score_items(products, ["スイーツ"])
        assert isinstance(items[0], RewardPoolItem)
        assert items[0].id == "item001"
        assert items[0].type == "product"

    def test_キーワードなし_デフォルトスコア05(self):
        products = [_make_product(review_avg=0.0, review_count=0)]
        items = score_items(products, [])
        assert items[0].score == 0.5


# ─────────────────────────────────────────
# merge_pool テスト
# ─────────────────────────────────────────
class TestMergePool:
    def test_新規アイテムが追加される(self):
        existing = []
        new_items = [_make_pool_item("001", score=0.8)]
        result = merge_pool(existing, new_items, max_items=20)
        assert len(result) == 1
        assert result[0].id == "001"

    def test_既存アイテムのスコアが更新される(self):
        existing = [_make_pool_item("001", score=0.3)]
        new_items = [_make_pool_item("001", score=0.9)]
        result = merge_pool(existing, new_items, max_items=20)
        assert len(result) == 1
        assert result[0].score == 0.9

    def test_今回取得にない既存アイテムは削除される(self):
        existing = [_make_pool_item("001"), _make_pool_item("002")]
        new_items = [_make_pool_item("001")]
        result = merge_pool(existing, new_items, max_items=20)
        assert len(result) == 1
        assert result[0].id == "001"

    def test_上位max_items件に絞られる(self):
        new_items = [_make_pool_item(f"item{i:03d}", score=i / 100.0) for i in range(30)]
        result = merge_pool([], new_items, max_items=20)
        assert len(result) == 20

    def test_スコア降順(self):
        new_items = [
            _make_pool_item("low", score=0.2),
            _make_pool_item("high", score=0.9),
            _make_pool_item("mid", score=0.5),
        ]
        result = merge_pool([], new_items, max_items=10)
        assert result[0].id == "high"
        assert result[-1].id == "low"


# ─────────────────────────────────────────
# adjust_score テスト
# ─────────────────────────────────────────
class TestAdjustScore:
    def _make_ddb_mock(self, items: list[RewardPoolItem]):
        """DynamoDBService のモックを作成する"""
        from models.schemas import RewardPool
        pool = RewardPool(
            pk="USER#test",
            items=items,
            updated_at="2026-05-16T00:00:00Z",
        )
        mock_ddb = MagicMock()
        mock_ddb.get_item.return_value = pool.model_dump()
        return mock_ddb

    def test_bought_でスコアが上がる(self):
        item = _make_pool_item("001", score=0.5)
        mock_ddb = self._make_ddb_mock([item])

        adjust_score("USER#test", "001", "bought", mock_ddb)

        put_call = mock_ddb.put_item.call_args
        pool_data = put_call[0][2]  # 3番目の引数が data
        updated_item = pool_data["items"][0]
        assert updated_item["score"] == pytest.approx(0.5 + 0.15)

    def test_skip_でスコアが下がる(self):
        item = _make_pool_item("001", score=0.5)
        mock_ddb = self._make_ddb_mock([item])

        adjust_score("USER#test", "001", "skip", mock_ddb)

        put_call = mock_ddb.put_item.call_args
        pool_data = put_call[0][2]
        updated_item = pool_data["items"][0]
        assert updated_item["score"] == pytest.approx(0.5 - 0.10)

    def test_スコアは1を超えない(self):
        item = _make_pool_item("001", score=0.95)
        mock_ddb = self._make_ddb_mock([item])

        adjust_score("USER#test", "001", "bought", mock_ddb)

        put_call = mock_ddb.put_item.call_args
        pool_data = put_call[0][2]
        updated_item = pool_data["items"][0]
        assert updated_item["score"] <= 1.0

    def test_スコアは0を下回らない(self):
        item = _make_pool_item("001", score=0.05)
        mock_ddb = self._make_ddb_mock([item])

        adjust_score("USER#test", "001", "skip", mock_ddb)

        put_call = mock_ddb.put_item.call_args
        pool_data = put_call[0][2]
        updated_item = pool_data["items"][0]
        assert updated_item["score"] >= 0.0

    def test_プールなし_early_return(self):
        mock_ddb = MagicMock()
        mock_ddb.get_item.return_value = None

        # 例外が発生しないことを確認
        adjust_score("USER#test", "001", "bought", mock_ddb)
        mock_ddb.put_item.assert_not_called()

    def test_item_id存在しない_early_return(self):
        item = _make_pool_item("other_item", score=0.5)
        mock_ddb = self._make_ddb_mock([item])

        adjust_score("USER#test", "NOT_EXIST", "bought", mock_ddb)
        mock_ddb.put_item.assert_not_called()


# ─────────────────────────────────────────
# score_hotels テスト
# ─────────────────────────────────────────
def _make_hotel(
    hotel_no: str = "12345",
    name: str = "東京ホテル",
    price: int = 8000,
    location: str = "東京",
    review_avg: float = 4.2,
    review_count: int = 50,
) -> RakutenHotel:
    return RakutenHotel(
        hotel_no=hotel_no,
        name=name,
        price=Decimal(str(price)),
        location=location,
        hotel_url=f"https://travel.rakuten.co.jp/hotel/{hotel_no}/",
        image_url=None,
        review_average=review_avg,
        review_count=review_count,
    )


class TestScoreHotels:
    def test_typeが_travel(self):
        hotels = [_make_hotel()]
        result = score_hotels(hotels, ["旅行"])
        assert result[0].type == "travel"

    def test_スコアは0以1以下(self):
        hotels = [_make_hotel()]
        result = score_hotels(hotels, ["スイーツ"])
        assert 0.0 <= result[0].score <= 1.0

    def test_キーワードマッチにり高スコア(self):
        h_match = _make_hotel(name="旅行向けホテル")
        h_nomatch = _make_hotel(hotel_no="99", name="なんでもない害虫")
        result = score_hotels([h_match, h_nomatch], ["旅行"])
        # マッチアイテムが高スコア
        matched = next(x for x in result if x.id == "12345")
        unmatched = next(x for x in result if x.id == "99")
        assert matched.score > unmatched.score

    def test_空リスト(self):
        assert score_hotels([], ["旅行"]) == []

    def test_RewardPoolItemに変換される(self):
        from models.schemas import RewardPoolItem
        hotels = [_make_hotel()]
        result = score_hotels(hotels, ["旅行"])
        assert isinstance(result[0], RewardPoolItem)
        assert result[0].id == "12345"


# ─────────────────────────────────────────
# score_restaurants テスト
# ─────────────────────────────────────────
from dataclasses import dataclass
from typing import Optional


@dataclass
class _FakeRestaurant:
    shop_id: str
    name: str
    price: Decimal
    genre_name: str
    shop_url: str
    image_url: Optional[str]
    station_name: str


class TestScoreRestaurants:
    def test_typeが_restaurant(self):
        r = _FakeRestaurant("R001", "奈良屋", Decimal("2000"), "和食", "https://example.com", None, "東京")
        result = score_restaurants([r], ["和食"])
        assert result[0].type == "restaurant"

    def test_空リスト(self):
        assert score_restaurants([], ["和食"]) == []

    def test_RewardPoolItemに変換される(self):
        from models.schemas import RewardPoolItem
        r = _FakeRestaurant("R001", "奈良屋", Decimal("2000"), "和食", "https://example.com", None, "")
        result = score_restaurants([r], ["和食"])
        assert isinstance(result[0], RewardPoolItem)


# ─────────────────────────────────────────
# apply_type_weights テスト
# ─────────────────────────────────────────
class TestApplyTypeWeights:
    def _make_typed_item(self, item_id, score, item_type):
        return _make_pool_item(item_id, score=score, item_type=item_type)

    def test_旅行カテゴリで_travelアイテムがブーストされる(self):
        product_item = self._make_typed_item("p1", 0.5, "product")
        travel_item = self._make_typed_item("t1", 0.5, "travel")

        result = apply_type_weights(
            [product_item, travel_item],
            pref_categories=["旅行でリフレッシュ"],
        )
        product_result = next(x for x in result if x.id == "p1")
        travel_result = next(x for x in result if x.id == "t1")
        assert travel_result.score > product_result.score

    def test_カテゴリなし_変更なし(self):
        items = [self._make_typed_item("p1", 0.5, "product")]
        result = apply_type_weights(items, pref_categories=[])
        assert result[0].score == pytest.approx(0.5)

    def test_スコアは1を超えない(self):
        item = self._make_typed_item("t1", 0.9, "travel")
        result = apply_type_weights([item], pref_categories=["旅行"])
        assert result[0].score <= 1.0

    def test_空リスト_そのまま返る(self):
        assert apply_type_weights([], ["旅行"]) == []
