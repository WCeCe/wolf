"""
狼队频道落刀后：将当夜协商压缩为一条摘要（每夜 1 次 LLM，全员狼人共用）。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

from llm.client import loader
from llm.structured import client_from_cfg

if TYPE_CHECKING:
    from game.models import GameState

logger = logging.getLogger("werewolf")

ChannelLine = Tuple[int, str]


def _fallback_summary(state: "GameState", target_id: int) -> str:
    return f"第{state.round}轮狼队：刀口 {target_id} 号。"


def summarize_wolf_channel(
    state: "GameState",
    channel_lines: List[ChannelLine],
    target_id: int,
    *,
    vote_summary: str | None = None,
) -> str:
    """
    根据当夜狼队频道发言与最终刀口生成一条中文摘要（≤120 字建议）。
    失败时返回规则 fallback。
    """
    fallback = _fallback_summary(state, target_id)
    if not channel_lines:
        return fallback

    cfg = loader.load_llm_config("werewolf")
    if not cfg.get("api_key"):
        logger.warning("狼队摘要：未配置 API Key，使用 fallback")
        return fallback

    dialogue = "\n".join(f"{pid}号狼队友: {text}" for pid, text in channel_lines)
    vote_block = vote_summary or f"表决：刀 {target_id} 号"
    user_prompt = (
        f"当前第{state.round}轮夜晚。狼队频道讨论记录：\n{dialogue}\n\n"
        f"【最终表决，以此为准】\n{vote_block}\n"
        f"最终刀口：{target_id} 号。\n"
        "请用一条中文总结（不超过120字）："
        "须写明表决得票情况；讨论若有分歧可简述，但刀口必须以表决为准，不得写与表决矛盾的刀口。"
        "可选一句白天伪装建议。只写已发生事实。"
    )

    try:
        client = client_from_cfg(cfg)
        response = client.chat.completions.create(
            model=cfg["model"],
            temperature=min(cfg.get("temperature", 0.7), 0.5),
            max_tokens=min(cfg.get("max_tokens", 500), 200),
            messages=[
                {
                    "role": "system",
                    "content": "你是狼人杀战报整理员，只输出一条简洁摘要，不要分点列表。",
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content.strip()
        if text:
            return text
    except Exception as e:
        logger.warning("狼队频道 LLM 摘要失败：%s", e)

    return fallback
