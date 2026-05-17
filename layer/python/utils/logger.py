"""
構造化ログ（PII マスク付き）

aws-lambda-powertools Logger をラップし、以下のフィールドを自動マスクする:
- LINE userId / user_id    : 先頭 6 文字 + "***"
- message / chat_content  : "[MASKED]"
- refresh_token           : "[MASKED]"
- access_token            : "[MASKED]"
- memo / raw_text         : "[MASKED]"
- calendar_* プレフィックス: "[MASKED]"
"""
from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger


# ─────────────────────────────────────────
# PII マスク設定
# ─────────────────────────────────────────
_PII_FULL_MASK_KEYS = frozenset(
    {
        "message",
        "chat_content",
        "refresh_token",
        "access_token",
        "memo",
        "raw_text",
        "authorization",
        "token",
    }
)

_PII_PARTIAL_MASK_KEYS = frozenset(
    {
        "line_user_id",
        "user_id",
        "userId",
        "lineUserId",
    }
)

_CALENDAR_PREFIX = "calendar_"


def _mask_user_id(value: str) -> str:
    """LINE userID: 先頭 6 文字 + '***'"""
    if value and len(value) > 6:
        return value[:6] + "***"
    return "***"


def _sanitize_extra(extra: dict[str, Any]) -> dict[str, Any]:
    """extra dict の PII フィールドをマスクして返す"""
    sanitized: dict[str, Any] = {}
    for key, val in extra.items():
        if key in _PII_FULL_MASK_KEYS or key.startswith(_CALENDAR_PREFIX):
            sanitized[key] = "[MASKED]"
        elif key in _PII_PARTIAL_MASK_KEYS:
            sanitized[key] = _mask_user_id(str(val)) if val else "[MASKED]"
        else:
            sanitized[key] = val
    return sanitized


# ─────────────────────────────────────────
# Logger ラッパークラス
# ─────────────────────────────────────────
class PIIMaskingLogger:
    """aws-lambda-powertools Logger + PII マスク"""

    def __init__(self, service: str) -> None:
        self._logger = Logger(
            service=service,
            level=os.environ.get("LOG_LEVEL", "INFO"),
        )

    def info(self, msg: str, **extra: Any) -> None:
        self._logger.info(msg, extra=_sanitize_extra(extra))

    def warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(msg, extra=_sanitize_extra(extra))

    def error(self, msg: str, **extra: Any) -> None:
        self._logger.error(msg, extra=_sanitize_extra(extra))

    def debug(self, msg: str, **extra: Any) -> None:
        self._logger.debug(msg, extra=_sanitize_extra(extra))

    def exception(self, msg: str, **extra: Any) -> None:
        self._logger.exception(msg, extra=_sanitize_extra(extra))


# ─────────────────────────────────────────
# シングルトンキャッシュ
# ─────────────────────────────────────────
_loggers: dict[str, PIIMaskingLogger] = {}


def get_logger(service: str) -> PIIMaskingLogger:
    """サービス名で PIIMaskingLogger インスタンスを返す（キャッシュあり）"""
    if service not in _loggers:
        _loggers[service] = PIIMaskingLogger(service)
    return _loggers[service]
