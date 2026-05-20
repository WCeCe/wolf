"""
结构化 LLM 调用的共享实现。

night / vote / witch 均采用「json_schema(strict) → json_object」回退链；
每种格式在传输失败时最多请求 2 次，仍失败则换下一格式或返回 None 由上层兜底。

失败回退顺序（本模块 + 各 night/vote 调用方）：
  1. json_schema（不支持则跳过）→ 每格式最多 2 次传输重试
  2. json_object → 每格式最多 2 次传输重试
  3. 上层：自由文本 + 正则（client.generate_player_response，亦有传输重试）
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Callable, Optional, TypeVar

from openai import OpenAI

from llm.retry import (
    MAX_TRANSPORT_ATTEMPTS,
    is_response_format_unavailable,
    is_retryable_transport_error,
    sleep_before_transport_retry,
)

logger = logging.getLogger("werewolf")

T = TypeVar("T")


@lru_cache(maxsize=8)
def get_openai_client(api_key: str, base_url: str) -> OpenAI:
    """
    按 (api_key, base_url) 缓存 OpenAI 客户端。

    一局内每名玩家可能多次调用 LLM，复用客户端可减少连接开销。
    base_url 为空串时表示使用官方默认 endpoint。
    """
    return OpenAI(api_key=api_key, base_url=base_url or None)


def client_from_cfg(cfg: dict) -> OpenAI:
    """从 load_llm_config 返回的字典构造（或命中缓存）客户端。"""
    return get_openai_client(cfg["api_key"], cfg.get("base_url") or "")


def call_structured_completion(
    cfg: dict,
    system_prompt: str,
    user_message: str,
    *,
    schema_name: str,
    json_schema: dict,
    parse_raw: Callable[[str], T | None],
    min_max_tokens: int = 80,
    json_object_first: bool = False,
) -> T | None:
    """
    依次尝试 json_schema(strict) 与 json_object，解析成功即返回。

    parse_raw: 将模型返回的 JSON 字符串解析为业务对象；非法则返回 None 以触发下一策略。
    """
    client = client_from_cfg(cfg)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    max_tokens = max(cfg.get("max_tokens", 150), min_max_tokens)

    json_schema_fmt: dict = {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": json_schema,
        },
    }
    json_object_fmt: dict = {"type": "json_object"}
    formats: list[dict] = (
        [json_object_fmt, json_schema_fmt]
        if json_object_first
        else [json_schema_fmt, json_object_fmt]
    )

    skip_json_schema = False
    last_raw: str | None = None

    for response_format in formats:
        fmt_type = response_format["type"]
        if fmt_type == "json_schema" and skip_json_schema:
            continue

        for attempt in range(MAX_TRANSPORT_ATTEMPTS):
            try:
                response = client.chat.completions.create(
                    model=cfg["model"],
                    temperature=cfg["temperature"],
                    max_tokens=max_tokens,
                    messages=messages,
                    response_format=response_format,
                )
                raw = response.choices[0].message.content
                if raw:
                    last_raw = raw
                    parsed = parse_raw(raw)
                    if parsed is not None:
                        return parsed
                    logger.debug(
                        "%s 返回内容无法解析（%s），换下一格式；片段: %s",
                        schema_name,
                        fmt_type,
                        raw[:200].replace("\n", " "),
                    )
                break
            except Exception as e:
                if fmt_type == "json_schema" and is_response_format_unavailable(e):
                    skip_json_schema = True
                    logger.debug(
                        "%s 不支持 json_schema，跳过至 json_object：%s",
                        schema_name,
                        e,
                    )
                    break
                if (
                    is_retryable_transport_error(e)
                    and attempt < MAX_TRANSPORT_ATTEMPTS - 1
                ):
                    logger.debug(
                        "%s 结构化传输失败（%s），%.1fs 后重试 (%s/%s)：%s",
                        schema_name,
                        fmt_type,
                        0.5 * (2**attempt),
                        attempt + 2,
                        MAX_TRANSPORT_ATTEMPTS,
                        e,
                    )
                    sleep_before_transport_retry(attempt)
                    continue
                logger.debug(
                    "%s 结构化调用失败（%s）：%s", schema_name, fmt_type, e
                )
                break

    if last_raw:
        logger.debug(
            "%s 全部结构化格式均未解析成功，最后片段: %s",
            schema_name,
            last_raw[:200].replace("\n", " "),
        )
    return None


def extract_target_id_from_text(raw: str, valid_ids: list[int]) -> Optional[int]:
    """从自由文本中提取第一个落在合法集合内的座位号（结构化失败时的兜底）。"""
    if not valid_ids:
        return None
    valid_set = set(valid_ids)
    for m in re.finditer(r"\b(\d+)\b", raw):
        n = int(m.group(1))
        if n in valid_set:
            return n
    return None
