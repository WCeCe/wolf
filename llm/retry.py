"""
LLM 传输层重试（非内容质量门阀）。

用于 Connection error、超时、5xx/429 等瞬时故障；
json_schema 不被提供商支持时由 structured 层跳过，不在此重试。

质量门阀（生成后本地校验 + 纠错再生成）仅保留在狼队频道 roles/werewolf.py。
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

logger = logging.getLogger("werewolf")

# 每种 response_format / 每次 completion：最多 2 次请求（首次 + 1 次重试）
MAX_TRANSPORT_ATTEMPTS = 2
INITIAL_BACKOFF_SEC = 0.5

T = TypeVar("T")


def is_response_format_unavailable(exc: BaseException) -> bool:
    """当前端点不支持 json_schema 等 strict 格式，应立刻换 json_object。"""
    text = str(exc).lower()
    if "response_format" in text and (
        "unavailable" in text or "invalid_request" in text
    ):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code == 400:
        if "response_format" in text or "json_schema" in text:
            return True
    return False


def is_retryable_transport_error(exc: BaseException) -> bool:
    if isinstance(
        exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)
    ):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in (
        408,
        409,
        429,
        500,
        502,
        503,
        504,
    ):
        return True
    text = str(exc).lower()
    return (
        "connection error" in text
        or "timed out" in text
        or "timeout" in text
        or "rate limit" in text
    )


def sleep_before_transport_retry(attempt_index: int) -> None:
    """attempt_index 从 0 起，对应第 1 次失败后的等待。"""
    time.sleep(INITIAL_BACKOFF_SEC * (2**attempt_index))


def call_with_transport_retries(
    call: Callable[[], T],
    *,
    label: str,
    max_attempts: int = MAX_TRANSPORT_ATTEMPTS,
) -> T:
    """执行 call；遇可重试传输错误时最多再试 max_attempts - 1 次。"""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return call()
        except Exception as e:
            last_exc = e
            if is_response_format_unavailable(e):
                raise
            if not is_retryable_transport_error(e) or attempt >= max_attempts - 1:
                raise
            logger.debug(
                "%s 传输错误，%.1fs 后重试 (%s/%s): %s",
                label,
                INITIAL_BACKOFF_SEC * (2**attempt),
                attempt + 2,
                max_attempts,
                e,
            )
            sleep_before_transport_retry(attempt)
    assert last_exc is not None
    raise last_exc
