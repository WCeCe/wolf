"""
投票放逐：结构化输出 target_id，与夜晚行动共用 schema 与 structured 模块。
"""
import logging
from typing import TYPE_CHECKING, Optional

from schemas.night_action import (
    NightTargetDecision,
    build_night_target_json_schema,
    parse_night_target_decision,
)

from utils.helpers import get_vote_candidates
from config.loader import PROMPT_TIER_COMPACT
from llm.client import generate_player_response, loader
from llm.prompt_format import build_user_message
from llm.structured import call_structured_completion, extract_target_id_from_text

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")


def _vote_user_message(
    player_id: int,
    player_name: str,
    role_key: str,
    context: str,
    round_num: int,
    candidates: list[int],
) -> str:
    action_prompt = loader.load_action_prompt("vote", role_key)
    task_part = loader.render_prompt(
        action_prompt,
        player_id=player_id,
        player_name=player_name,
        round=round_num,
    )
    body = build_user_message(task_part, context)
    return (
        f"{body}\n\n"
        f"【结构化输出】投票放逐一名玩家。target_id 必须是以下之一：{candidates}。\n"
        f"请输出 JSON 对象，包含字段 target_id（整数）、reason（字符串，不超过30字）。"
    )


def generate_vote(
    player: "Player",
    role_key: str,
    state: "GameState",
    context: str | None = None,
) -> Optional[int]:
    """返回被投票玩家的 player_id，失败时返回 None。"""
    candidates = get_vote_candidates(state, player.player_id)
    if not candidates:
        return None

    if context is None:
        context = f"当前第{state.round}轮投票。"

    cfg = loader.load_llm_config(role_key)
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = loader.load_system_prompt(role_key, PROMPT_TIER_COMPACT)
    user_message = _vote_user_message(
        player.player_id,
        player.name,
        role_key,
        context,
        state.round,
        candidates,
    )

    schema = build_night_target_json_schema(candidates)

    def _parse(raw: str) -> NightTargetDecision | None:
        return parse_night_target_decision(raw, candidates)

    decision = call_structured_completion(
        cfg,
        system_prompt,
        user_message,
        schema_name="vote_target_decision",
        json_schema=schema,
        parse_raw=_parse,
    )
    if decision is not None:
        logger.debug(
            "%s 投票决策 target_id=%s reason=%s",
            player.name,
            decision.target_id,
            decision.reason,
        )
        return decision.target_id

    logger.warning("%s 结构化投票失败，尝试自由文本兜底", player.name)
    raw = generate_player_response(
        player.name,
        role_key,
        "vote",
        user_message,
        state.round,
        player_id=player.player_id,
    )
    return extract_target_id_from_text(raw, candidates)
