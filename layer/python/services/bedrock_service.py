"""
Bedrock サービス — テキスト/画像推論の抽象化

設計方針:
- Amazon Nova Micro（テキスト）/ Nova Lite（画像）の呼び出しを提供
- モデル ID は環境変数から取得（切り替え可能設計）
- ThrottlingException / ServiceUnavailableException に対して指数バックオフリトライ（最大 3 回）
- LINE API と異なりリトライ可（冪等性あり）
"""
from __future__ import annotations

import os
import time
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from utils.exceptions import BedrockError
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# リトライ設定
# ─────────────────────────────────────────
# リトライ設定（Lambda の29s制限内に収めるため1回のみ）
_RETRY_DELAYS = [0.5, 1.0]  # 最大2試行（初回 + 1リトライ）
_RETRYABLE_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelStreamErrorException",
    }
)


class BedrockService:
    """Amazon Bedrock Converse API ラッパー"""

    def __init__(self) -> None:
        # connect_timeout=5s, read_timeout=20s: Lambda 29s制限内で2回Bedrockを呼べるように設定
        _config = Config(
            connect_timeout=5,
            read_timeout=20,
            retries={"max_attempts": 1},  # boto3自動リトライなし（アプリ側で制御）
        )
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
            config=_config,
        )
        self.default_text_model = os.environ.get(
            "BEDROCK_TEXT_MODEL_ID", "amazon.nova-lite-v1:0"
        )
        self.default_image_model = os.environ.get(
            "BEDROCK_IMAGE_MODEL_ID", "amazon.nova-lite-v1:0"
        )
        self.fallback_model = os.environ.get(
            "BEDROCK_FALLBACK_MODEL_ID", "amazon.nova-lite-v1:0"
        )

    # ─────────────────────────────────────────
    # 公開メソッド
    # ─────────────────────────────────────────

    def invoke_text(
        self,
        prompt: str,
        model_id: str = None,
        max_tokens: int = 1000,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        テキスト推論を実行する

        Args:
            prompt: ユーザーターンのプロンプト文字列
            model_id: Bedrock モデル ID（None の場合は環境変数から取得）
            max_tokens: 最大生成トークン数
            system_prompt: システムプロンプト（Converse API の system フィールド）
            temperature: サンプリング温度（0.0〜1.0）

        Returns:
            生成されたテキスト

        Raises:
            BedrockError: API 呼び出し失敗時（リトライ後も失敗した場合）
        """
        resolved_model = model_id or self.default_text_model
        logger.info("invoke_text start", model_id=resolved_model)

        def _call() -> str:
            kwargs: dict = {
                "modelId": resolved_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
            }
            if system_prompt:
                kwargs["system"] = [{"text": system_prompt}]
            response = self._client.converse(**kwargs)
            return response["output"]["message"]["content"][0]["text"]

        return self._invoke_with_retry(_call)

    def invoke_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str = "image/jpeg",
        model_id: str = None,
        max_tokens: int = 1000,
    ) -> str:
        """
        画像 + テキスト推論を実行する

        Args:
            prompt: プロンプト文字列
            image_bytes: 画像バイナリ
            media_type: 画像 MIME タイプ（"image/jpeg" | "image/png" 等）
            model_id: Bedrock モデル ID（None の場合は環境変数から取得）
            max_tokens: 最大生成トークン数

        Returns:
            生成されたテキスト

        Raises:
            BedrockError: API 呼び出し失敗時
        """
        resolved_model = model_id or self.default_image_model
        image_format = media_type.split("/")[-1]  # "jpeg" | "png"
        logger.info("invoke_image start", model_id=resolved_model)

        def _call() -> str:
            response = self._client.converse(
                modelId=resolved_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": image_format,
                                    "source": {"bytes": image_bytes},
                                }
                            },
                            {"text": prompt},
                        ],
                    }
                ],
                inferenceConfig={"maxTokens": max_tokens},
            )
            return response["output"]["message"]["content"][0]["text"]

        return self._invoke_with_retry(_call)

    # ─────────────────────────────────────────
    # 内部メソッド
    # ─────────────────────────────────────────

    def _invoke_with_retry(self, invoke_fn) -> str:
        """指数バックオフリトライ（最大 3 回）"""
        last_error: Optional[Exception] = None

        for attempt, delay in enumerate(_RETRY_DELAYS):
            try:
                return invoke_fn()
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code not in _RETRYABLE_ERROR_CODES:
                    detail = e.response["Error"].get("Message", "")
                    logger.error(
                        "bedrock_non_retryable_error",
                        error_code=error_code,
                        detail=detail,
                    )
                    raise BedrockError(
                        f"Bedrock 非リトライエラー: {error_code} - {detail}", e
                    ) from e
                last_error = e
                logger.warning(
                    "Bedrock リトライ",
                    attempt=attempt + 1,
                    error_code=error_code,
                    next_delay=delay,
                )
                if attempt < len(_RETRY_DELAYS) - 1:
                    time.sleep(delay)

        raise BedrockError(
            f"Bedrock API リトライ上限到達（{len(_RETRY_DELAYS)} 回）", last_error
        )


# ─────────────────────────────────────────
# モジュールレベルシングルトン
# ─────────────────────────────────────────
_instance: Optional[BedrockService] = None


def get_bedrock_service() -> BedrockService:
    """BedrockService シングルトンを返す"""
    global _instance
    if _instance is None:
        _instance = BedrockService()
    return _instance
