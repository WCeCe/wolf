"""
5.4 白天公聊生成长度：prompt 引导 + phase 级 max_tokens。

不做 publish 写时截断；超长由 prompt 与 max_tokens 约束，超阈值仅打 warning（GB-007）。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("werewolf")

DISCUSS_CHAR_MIN = 120
DISCUSS_CHAR_MAX = 180
DISCUSS_WARN_CHARS = 250
DISCUSS_MAX_TOKENS_DEFAULT = 180
WEREWOLF_CHANNEL_MAX_TOKENS_DEFAULT = 100


def discuss_length_instruction() -> str:
    """拼入 discuss action 的 instruction，与常量单源一致。"""
    return (
        f"公聊须为一段完整话（约{DISCUSS_CHAR_MIN}～{DISCUSS_CHAR_MAX}字），"
        "收束成明确态度或质疑对象；禁止分点长文、"
        "禁止复述【局面与记忆】中的大段原文。"
    )


def warn_if_speech_too_long(
    speech: str,
    *,
    player_name: str,
    phase: str,
) -> str:
    """超长发言打 warning，不修改原文（GB-007）。"""
    n = len(speech or "")
    if n > DISCUSS_WARN_CHARS:
        logger.warning(
            "%s %s 发言约 %s 字，超过建议上限 %s（未截断）",
            player_name,
            phase,
            n,
            DISCUSS_WARN_CHARS,
        )
    return speech


def max_tokens_for_phase(cfg: dict, phase: str) -> int:
    """按阶段取 max_tokens；未配置时回退 profile 的 max_tokens。"""
    base = int(cfg.get("max_tokens", 500))
    if phase in ("discuss", "last_words"):
        return int(cfg.get("discuss_max_tokens", DISCUSS_MAX_TOKENS_DEFAULT))
    if phase == "werewolf_channel":
        return int(
            cfg.get("werewolf_channel_max_tokens", WEREWOLF_CHANNEL_MAX_TOKENS_DEFAULT)
        )
    return base
