"""
reward_pool_updater ユニットテスト

DynamoDBService・rakuten_service をモック化して Lambda ハンドラの動作を検証する。
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

# パス設定（src/ を先頭に追加。layer/python は conftest.py が末尾に追加済み）
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "src"),
)

from models.schemas import (
    ENTITY_PROFILE,
    PrefMemory,
    RewardPool,
    RewardPoolItem,
    SK_PREFIX_REWARD_POOL,
    SK_PREF_MEMORY,
)
from services.rakuten_service import RakutenAPIError, RakutenProduct


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def _make_profile_item(pk: str) -> dict:
    return {
        "PK": pk,
        "SK": "PROFILE#",
        "entity_type": "PROFILE",
        "status": "ACTIVE",
        "tone": "friendly",
        "push_count_this_month": 0,
    }


def _make_rakuten_product(item_id: str = "item001", name: str = "スイーツ", price: int = 980) -> RakutenProduct:
    return RakutenProduct(
        item_id=item_id,
        name=name,
        price=Decimal(str(price)),
        category_name="スイーツ",
        item_url=f"https://example.com/{item_id}",
        image_url=None,
        shop_name="TestShop",
        review_average=4.5,
        review_count=50,
    )


def _make_ddb_mock(user_pks: list[str], pref_raw: dict | None = None, pool_raw: dict | None = None) -> MagicMock:
    """
    DynamoDBService のモックを作成する。

    Args:
        user_pks:  GSI query が返す PROFILE アイテムの PK リスト
        pref_raw:  get_item("PREF_MEMORY#") の返り値（None の場合はプロファイルなし）
        pool_raw:  get_item("REWARD_POOL#") の返り値（None の場合はプール未作成）
    """
    mock_ddb = MagicMock()

    # GSI query: PROFILE エンティティ一覧
    mock_ddb.query_by_gsi.return_value = [_make_profile_item(pk) for pk in user_pks]

    # get_item は SK によって返す値を分岐
    def get_item_side_effect(pk: str, sk: str):
        if sk == SK_PREF_MEMORY:
            return pref_raw
        if sk == SK_PREFIX_REWARD_POOL:
            return pool_raw
        return None

    mock_ddb.get_item.side_effect = get_item_side_effect
    return mock_ddb


# ─────────────────────────────────────────
# lambda_handler テスト
# ─────────────────────────────────────────
class TestLambdaHandler:

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_正常系_1ユーザー更新成功(self, mock_search, mock_get_ddb):
        """1 ユーザーのプールが正常に更新されること"""
        from handlers.reward_pool_updater import lambda_handler

        products = [_make_rakuten_product()]
        mock_search.return_value = products

        mock_ddb = _make_ddb_mock(["USER#user1"])
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        # DynamoDB put_item が呼ばれたことを確認
        mock_ddb.put_item.assert_called_once()
        call_args = mock_ddb.put_item.call_args
        assert call_args[0][0] == "USER#user1"
        assert call_args[0][1] == SK_PREFIX_REWARD_POOL

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_正常系_複数ユーザー全員更新(self, mock_search, mock_get_ddb):
        """3 ユーザー全員のプールが更新されること"""
        from handlers.reward_pool_updater import lambda_handler

        mock_search.return_value = [_make_rakuten_product()]
        mock_ddb = _make_ddb_mock(["USER#u1", "USER#u2", "USER#u3"])
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        assert mock_ddb.put_item.call_count == 3

    @patch("handlers.reward_pool_updater._update_user_pool")
    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    def test_楽天APIエラー時_他ユーザーは継続(self, mock_get_ddb, mock_update_pool):
        """ユーザー u1 で RakutenAPIError が発生しても、u2 の処理は継続すること"""
        from handlers.reward_pool_updater import lambda_handler

        def update_side_effect(user_pk, ddb):
            if user_pk == "USER#u1":
                raise RakutenAPIError("全キーワード失敗")
            return 2  # u2 は成功

        mock_update_pool.side_effect = update_side_effect
        mock_ddb = _make_ddb_mock(["USER#u1", "USER#u2"])
        mock_get_ddb.return_value = mock_ddb

        # 例外が伝播しないことを確認（Lambda は正常終了）
        lambda_handler({}, None)

        # _update_user_pool が 2 ユーザー分呼び出されること
        assert mock_update_pool.call_count == 2

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_ユーザーなし_正常終了(self, mock_search, mock_get_ddb):
        """PROFILE が 1 件もない場合でも正常終了すること"""
        from handlers.reward_pool_updater import lambda_handler

        mock_ddb = _make_ddb_mock([])
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        mock_ddb.put_item.assert_not_called()
        mock_search.assert_not_called()

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_嗜好なしユーザー_デフォルトキーワードで検索(self, mock_search, mock_get_ddb):
        """PREF_MEMORY# がないユーザーはデフォルトキーワードで楽天検索すること"""
        from handlers.reward_pool_updater import lambda_handler, DEFAULT_KEYWORDS

        mock_search.return_value = [_make_rakuten_product()]
        # pref_raw=None → 嗜好なし
        mock_ddb = _make_ddb_mock(["USER#u1"], pref_raw=None)
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        # search_products が DEFAULT_KEYWORDS の件数分呼ばれること
        assert mock_search.call_count == len(DEFAULT_KEYWORDS)

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_既存プール_差分マージされる(self, mock_search, mock_get_ddb):
        """既存の REWARD_POOL# がある場合、差分マージされて保存されること"""
        from handlers.reward_pool_updater import lambda_handler

        existing_pool = RewardPool(
            pk="USER#u1",
            items=[
                RewardPoolItem(id="old001", name="古い商品", price=Decimal("500"), category="スイーツ", score=0.7, type="product")
            ],
            updated_at="2026-05-15T00:00:00Z",
        )

        mock_search.return_value = [_make_rakuten_product("old001", "古い商品（更新後）")]
        mock_ddb = _make_ddb_mock(
            ["USER#u1"],
            pool_raw=existing_pool.model_dump(),
        )
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        put_call = mock_ddb.put_item.call_args
        saved_items = put_call[0][2]["items"]
        # 既存 item_id が更新されていること
        assert any(item["id"] == "old001" for item in saved_items)

    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_楽天API全失敗_既存プール保持(self, mock_search, mock_get_ddb):
        """楽天 API が全失敗した場合、DynamoDB への書き込みは行わないこと（既存プール保持）"""
        from handlers.reward_pool_updater import lambda_handler

        mock_search.side_effect = RakutenAPIError("全失敗")
        mock_ddb = _make_ddb_mock(["USER#u1"])
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        mock_ddb.put_item.assert_not_called()

    @patch("handlers.reward_pool_updater.MAX_RAKUTEN_REQUESTS", 0)
    @patch("handlers.reward_pool_updater.get_dynamodb_service")
    @patch("handlers.reward_pool_updater.search_products")
    def test_リクエスト上限_残りユーザーをスキップ(self, mock_search, mock_get_ddb):
        """MAX_RAKUTEN_REQUESTS に達したら残りのユーザーをスキップすること"""
        from handlers.reward_pool_updater import lambda_handler

        mock_ddb = _make_ddb_mock(["USER#u1", "USER#u2"])
        mock_get_ddb.return_value = mock_ddb

        lambda_handler({}, None)

        # 上限0なので全ユーザーがスキップされ、search も put も呼ばれない
        mock_search.assert_not_called()
        mock_ddb.put_item.assert_not_called()


# ─────────────────────────────────────────
# _get_all_user_pks テスト
# ─────────────────────────────────────────
class TestGetAllUserPks:
    def test_アクティブユーザーPKリストを返す(self):
        from handlers.reward_pool_updater import _get_all_user_pks

        mock_ddb = MagicMock()
        mock_ddb.query_by_gsi.return_value = [
            {"PK": "USER#abc", "SK": "PROFILE#", "entity_type": "PROFILE", "status": "ACTIVE"},
            {"PK": "USER#def", "SK": "PROFILE#", "entity_type": "PROFILE", "status": "ACTIVE"},
        ]

        pks = _get_all_user_pks(mock_ddb)

        assert pks == ["USER#abc", "USER#def"]
        mock_ddb.query_by_gsi.assert_called_once_with(
            entity_type=ENTITY_PROFILE,
            filter_expr={"status": "ACTIVE"},
        )

    def test_結果なし_空リスト(self):
        from handlers.reward_pool_updater import _get_all_user_pks

        mock_ddb = MagicMock()
        mock_ddb.query_by_gsi.return_value = []

        pks = _get_all_user_pks(mock_ddb)

        assert pks == []

    def test_PKフィールドなし_スキップ(self):
        from handlers.reward_pool_updater import _get_all_user_pks

        mock_ddb = MagicMock()
        mock_ddb.query_by_gsi.return_value = [
            {"SK": "PROFILE#"},   # PK なし → スキップ
            {"PK": "USER#valid", "SK": "PROFILE#"},
        ]

        pks = _get_all_user_pks(mock_ddb)

        assert pks == ["USER#valid"]


# ─────────────────────────────────────────
# _update_user_pool テスト
# ─────────────────────────────────────────
class TestUpdateUserPool:
    @patch("handlers.reward_pool_updater.search_products")
    def test_正常系_items数を返す(self, mock_search):
        from handlers.reward_pool_updater import _update_user_pool, DEFAULT_KEYWORDS

        products = [
            _make_rakuten_product("p1"),
            _make_rakuten_product("p2"),
        ]
        mock_search.return_value = products
        mock_ddb = _make_ddb_mock([])

        count = _update_user_pool("USER#test", mock_ddb)

        # DEFAULT_KEYWORDSの件数分検索 × 2商品 = 合計取得数
        expected = len(DEFAULT_KEYWORDS) * len(products)
        assert count == expected
        mock_ddb.put_item.assert_called_once()

    @patch("handlers.reward_pool_updater.search_products")
    def test_全キーワード失敗_RakutenAPIError(self, mock_search):
        from handlers.reward_pool_updater import _update_user_pool

        mock_search.side_effect = RakutenAPIError("失敗")
        mock_ddb = _make_ddb_mock([])

        with pytest.raises(RakutenAPIError):
            _update_user_pool("USER#test", mock_ddb)

    @patch("handlers.reward_pool_updater.search_products")
    def test_updated_atが保存される(self, mock_search):
        from handlers.reward_pool_updater import _update_user_pool

        mock_search.return_value = [_make_rakuten_product()]
        mock_ddb = _make_ddb_mock([])

        _update_user_pool("USER#test", mock_ddb)

        put_call = mock_ddb.put_item.call_args
        pool_data = put_call[0][2]
        assert "updated_at" in pool_data
        assert pool_data["updated_at"].endswith("Z")
