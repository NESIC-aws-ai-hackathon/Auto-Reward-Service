"""
ユニットテスト共通フィクスチャ

テスト実行時は layer/python をパスに追加して Layer モジュールを import できるようにする。
"""
import os
import sys

import pytest

# layer/python を sys.path に追加（末尾: システムインストール済みパッケージを優先させる）
# 理由: layer/python には Lambda 用 Linux バイナリが含まれており、
#       Windows テスト環境では pydantic_core 等のネイティブ拡張が動作しない。
#       システムの pydantic (pip install pydantic) を優先させることで解決する。
_LAYER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "layer", "python"
)
_layer_abs = os.path.abspath(_LAYER_PATH)
if _layer_abs not in sys.path:
    sys.path.append(_layer_abs)

# src/handlers を sys.path に追加（webhook_handler 等のテスト用）
_HANDLERS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "handlers"
)
sys.path.insert(0, os.path.abspath(_HANDLERS_PATH))

# src/ を sys.path に追加（from prompts.xxx import ... の解決用）
_SRC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "src"
)
sys.path.insert(0, os.path.abspath(_SRC_PATH))


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """テスト用 AWS 環境変数を設定するフィクスチャ"""
    monkeypatch.setenv("TABLE_NAME", "ArsTable-test")
    monkeypatch.setenv("LINE_SECRET_NAME", "ars/line")
    monkeypatch.setenv("GOOGLE_SECRET_NAME", "ars/google")
    monkeypatch.setenv("RAKUTEN_SECRET_NAME", "ars/rakuten")
    monkeypatch.setenv("BEDROCK_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")
    monkeypatch.setenv("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-lite-v1:0")
    monkeypatch.setenv("BEDROCK_FALLBACK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DAILY_CHAT_LIMIT", "50")
    monkeypatch.setenv("RAKUTEN_DEFAULT_KEYWORDS", "スイーツ,コスメ,本,入浴剤,アロマ")
    monkeypatch.setenv("RAKUTEN_MAX_ITEMS_PER_POOL", "20")
    monkeypatch.setenv("RAKUTEN_HITS_PER_KEYWORD", "5")
    monkeypatch.setenv("HOTPEPPER_SECRET_NAME", "ars/hotpepper/api-key")
    monkeypatch.setenv("ENABLE_HOTEL_SEARCH", "false")   # テストではデフォルト無効
    monkeypatch.setenv("HOTEL_HITS_PER_KEYWORD", "3")
    monkeypatch.setenv("ENABLE_RESTAURANT_SEARCH", "false")  # テストではデフォルト無効
    monkeypatch.setenv("RESTAURANT_HITS_PER_KEYWORD", "3")
    monkeypatch.setenv("LIFF_CHANNEL_ID", "1234567890")
