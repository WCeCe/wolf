"""
狼队夜晚刀口投票：结构化 target_id（与白天投票共用 schema）。

投票上下文保持精简，避免长记忆导致 JSON 截断；失败时讨论推断 → 轻量 json 调用。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from config.loader import PROMPT_TIER_COMPACT
from llm.client import loader
from llm.prompt_format import build_user_message
from llm.structured import (
    call_structured_completion,
    client_from_cfg,
    extract_target_id_from_text,
)
from schemas.night_action import (
    NightTargetDecision,
    build_night_target_json_schema,
    parse_night_target_decision,
)
from utils.target_parse import channel_primary_targets, parse_target_ids
from utils.wolf_vote import ChannelLine

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")

_VOTE_SYSTEM_APPEND = (
    "【输出】仅回复一个 JSON 对象，不要 markdown、不要解释。"
    '格式：{"target_id": 座位整数, "reason": "不超过20字"}。'
)


def _wolf_vote_user_message(
    player_id: int,
    player_name: str,
    context: str,
    round_num: int,
    candidates: list[int],
) -> str:
    action_prompt = loader.load_action_prompt("wolf_kill_vote", "werewolf")
    task_part = loader.render_prompt(
        action_prompt,
        player_id=player_id,
        player_name=player_name,
        round=round_num,
    )
    body = build_user_message(task_part, context)
    return (
        f"{body}\n\n"
        f"【结构化输出】狼队刀口投票。target_id 必须是以下之一：{candidates}。\n"
        f"请输出 JSON：target_id（整数）、reason（字符串，不超过20字）。"
    )


def vote_target_from_discussion(
    player_id: int,
    channel_lines: List[ChannelLine],
    killable_ids: list[int],
) -> Optional[int]:
    """从该狼在讨论阶段的表述推断主刀口（结构化失败时的零 API 兜底）。"""
    for pid, text in channel_lines:
        if pid == player_id:
            ids = parse_target_ids(text, killable_ids)
            if ids:
                return ids[0]
    return None


def _compact_json_object_vote(
    cfg: dict,
    user_message: str,
    killable_ids: list[int],
    label: str,
) -> Optional[int]:
    """单次 json_object 轻量请求，避免走全文 generate_player_response。"""
    client = client_from_cfg(cfg)
    vote_cfg = {**cfg, "temperature": min(cfg.get("temperature", 0.7), 0.35)}

    def _create() -> str:
        response = client.chat.completions.create(
            model=vote_cfg["model"],
            temperature=vote_cfg["temperature"],
            max_tokens=96,
            messages=[
                {
                    "role": "system",
                    "content": "你是狼人杀狼队投票器。" + _VOTE_SYSTEM_APPEND,
                },
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        return (response.choices[0].message.content or "").strip()

    try:
        from llm.retry import call_with_transport_retries

        raw = call_with_transport_retries(_create, label=label)
        decision = parse_night_target_decision(raw, killable_ids)
        if decision is not None:
            return decision.target_id
        return extract_target_id_from_text(raw, killable_ids)
    except Exception as e:
        logger.debug("%s 轻量 json_object 投票失败：%s", label, e)
        return None


def generate_wolf_kill_vote(
    player: "Player",
    state: "GameState",
    context: str,
    killable_ids: list[int],
    channel_lines: List[ChannelLine],
) -> Optional[int]:
    """返回投票刀口 target_id；失败返回 None（由调用方继续兜底）。"""
    if not killable_ids:
        return None

    cfg = loader.load_llm_config("werewolf")
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = (
        loader.load_system_prompt("werewolf", PROMPT_TIER_COMPACT) + "\n" + _VOTE_SYSTEM_APPEND
    )
    user_message = _wolf_vote_user_message(
        player.player_id,
        player.name,
        context,
        state.round,
        killable_ids,
    )

    schema = build_night_target_json_schema(killable_ids)

    def _parse(raw: str) -> NightTargetDecision | None:
        return parse_night_target_decision(raw, killable_ids)

    decision = call_structured_completion(
        cfg,
        system_prompt,
        user_message,
        schema_name="wolf_kill_vote",
        json_schema=schema,
        parse_raw=_parse,
        min_max_tokens=128,
        json_object_first=True,
    )
    if decision is not None:
        logger.debug(
            "%s 狼队投票 target_id=%s reason=%s",
            player.name,
            decision.target_id,
            decision.reason,
        )
        return decision.target_id

    target_id = _compact_json_object_vote(
        cfg, user_message, killable_ids, label=f"{player.name}/wolf_vote_compact"
    )
    if target_id is not None:
        logger.info("%s 狼队投票经轻量 json_object 成功：%s 号", player.name, target_id)
        return target_id

    target_id = vote_target_from_discussion(
        player.player_id, channel_lines, killable_ids
    )
    if target_id is not None:
        logger.info(
            "%s 狼队投票结构化失败，采用讨论阶段主刀口：%s 号",
            player.name,
            target_id,
        )
        return target_id

    logger.warning(
        "%s 狼队投票结构化失败且无讨论刀口可推断（已跳过全文兜底以省 token）",
        player.name,
    )
    return None


def collect_wolf_kill_votes(
    state: "GameState",
    wolves: List["Player"],
    speak_order: List["Player"],
    channel_lines: List[ChannelLine],
    killable_ids: list[int],
    build_context: Callable,
) -> Dict[int, Optional[int]]:
    """
    按 speak_order 依次收集各狼投票。

    build_context: (state, wolf, channel_lines, killable_ids) -> str
    """
    import random

    from memory.publish import publish_werewolf

    # 讨论阶段主刀口分布，供日志对比
    primaries = channel_primary_targets(channel_lines, killable_ids)
    if primaries:
        logger.debug("讨论主刀口分布: %s", primaries)

    votes: Dict[int, Optional[int]] = {}
    for wolf in speak_order:
        try:
            ctx = build_context(state, wolf, channel_lines, killable_ids)
            target_id = generate_wolf_kill_vote(
                wolf, state, ctx, killable_ids, channel_lines
            )
        except Exception as e:
            logger.warning("%s 狼队投票失败：%s", wolf.name, e)
            target_id = None

        if target_id is None or target_id not in killable_ids:
            target_id = vote_target_from_discussion(
                wolf.player_id, channel_lines, killable_ids
            )
        if target_id is None or target_id not in killable_ids:
            target_id = random.choice(killable_ids)
            logger.warning("%s 狼队投票无效，随机投 %s 号", wolf.name, target_id)

        votes[wolf.player_id] = target_id
        publish_werewolf(
            state,
            f"投票刀 {target_id} 号。",
            sender=str(wolf.player_id),
            data_type="action",
        )
        logger.info("%s 狼队投票：%s 号", wolf.name, target_id)

    return votes
