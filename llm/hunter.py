"""
猎人死亡开枪：结构化选择 target_id。
"""
import logging
from typing import TYPE_CHECKING, Optional

from config.loader import PROMPT_TIER_COMPACT
from utils.helpers import get_hunter_shoot_candidates
from llm.client import loader
from llm.prompt_format import build_user_message
from llm.structured import call_structured_completion, extract_target_id_from_text
from schemas.night_action import (
    NightTargetDecision,
    build_night_target_json_schema,
    parse_night_target_decision,
)

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")

_CAUSE_LABEL = {"night": "昨夜死亡", "vote": "被投票放逐"}


def _hunter_shoot_user_message(
    player_id: int,
    player_name: str,
    context: str,
    round_num: int,
    candidates: list[int],
    cause: str,
) -> str:
    action_prompt = loader.load_action_prompt("hunter_shoot", "hunter")
    cause_label = _CAUSE_LABEL.get(cause, "出局")
    task_part = loader.render_prompt(
        action_prompt,
        player_id=player_id,
        player_name=player_name,
        round=round_num,
        cause_label=cause_label,
    )
    body = build_user_message(task_part, context)
    return (
        f"{body}\n\n"
        f"【结构化输出】选择开枪目标。target_id 必须是以下之一：{candidates}。\n"
        f"请输出 JSON 对象，包含字段 target_id（整数）、reason（字符串）。"
    )


def generate_hunter_shoot(
    player: "Player",
    state: "GameState",
    context: str,
    cause: str,
) -> Optional[int]:
    """猎人开枪，返回目标 player_id；失败返回 None。"""
    candidates = get_hunter_shoot_candidates(state)
    if not candidates:
        return None

    role_key = "hunter"
    cfg = loader.load_llm_config(role_key)
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = loader.load_system_prompt(role_key, PROMPT_TIER_COMPACT)
    user_message = _hunter_shoot_user_message(
        player.player_id,
        player.name,
        context,
        state.round,
        candidates,
        cause,
    )
    schema = build_night_target_json_schema(candidates)

    def _parse(raw: str) -> NightTargetDecision | None:
        return parse_night_target_decision(raw, candidates)

    decision = call_structured_completion(
        cfg,
        system_prompt,
        user_message,
        schema_name="hunter_shoot_decision",
        json_schema=schema,
        parse_raw=_parse,
    )
    if decision is not None:
        logger.debug(
            "猎人 %s 开枪决策 target_id=%s reason=%s",
            player.name,
            decision.target_id,
            decision.reason,
        )
        return decision.target_id

    logger.warning("猎人 %s 结构化开枪失败，尝试文本兜底", player.name)
    from llm.client import generate_player_response

    raw = generate_player_response(
        player.name,
        role_key,
        "hunter_shoot",
        user_message,
        state.round,
        player_id=player.player_id,
    )
    return extract_target_id_from_text(raw, candidates)
