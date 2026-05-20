"""
女巫夜晚行动：解药（救狼刀目标）+ 毒药。

在狼人刀口与预言家查验之后调用；结果写入 state.night_actions：
  witch_save: bool
  witch_poison: int | None
"""
import logging
from typing import TYPE_CHECKING, Optional

from schemas.witch_action import (
    POISON_SKIP,
    WitchNightDecision,
    build_witch_night_json_schema,
    parse_witch_night_decision,
)

from config.loader import PROMPT_TIER_COMPACT
from llm.client import loader
from llm.prompt_format import build_user_message
from llm.structured import call_structured_completion

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")


def _witch_user_message(
    player_name: str,
    context: str,
    round_num: int,
    *,
    can_use_antidote: bool,
    wolf_kill_id: Optional[int],
    poison_candidates: list[int],
) -> str:
    action_prompt = loader.load_action_prompt("night", "witch")
    task_part = loader.render_prompt(
        action_prompt,
        player_name=player_name,
        round=round_num,
    )
    body = build_user_message(task_part, context)
    knife = f"{wolf_kill_id} 号" if wolf_kill_id else "（本夜无人被狼人刀中）"
    antidote_hint = "可使用解药救回刀口目标" if can_use_antidote else "解药不可用（已用完或今夜无刀口）"
    poison_enum = [POISON_SKIP] + poison_candidates
    return (
        f"{body}\n\n"
        f"【女巫行动约束】今夜狼人刀口：{knife}。{antidote_hint}。\n"
        f"毒药可选目标编号（0 表示本夜不毒）：{poison_enum}。\n"
        f"请输出 JSON：use_antidote（bool）、poison_target_id（int，0 为不毒）、reason（str）。"
    )


def generate_witch_night_action(
    witch: "Player",
    state: "GameState",
    context: str,
    *,
    can_use_antidote: bool,
    wolf_kill_id: Optional[int],
    poison_candidates: list[int],
) -> WitchNightDecision:
    """
    请求女巫本夜决策。LLM 失败时返回保守默认：不救、不毒。
    """
    cfg = loader.load_llm_config("witch")
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = loader.load_system_prompt("witch", PROMPT_TIER_COMPACT)
    user_message = _witch_user_message(
        witch.name,
        context,
        state.round,
        can_use_antidote=can_use_antidote,
        wolf_kill_id=wolf_kill_id,
        poison_candidates=poison_candidates,
    )
    user_message = (
        "【女巫行动】你可选择是否用解药救今夜狼刀目标、"
        "是否用毒药毒杀一名存活玩家（编号 0 表示不毒）。\n\n"
        + user_message
    )

    schema = build_witch_night_json_schema(poison_candidates)

    def _parse(raw: str) -> WitchNightDecision | None:
        return parse_witch_night_decision(
            raw, poison_candidates, can_use_antidote=can_use_antidote
        )

    decision = call_structured_completion(
        cfg,
        system_prompt,
        user_message,
        schema_name="witch_night_decision",
        json_schema=schema,
        parse_raw=_parse,
        min_max_tokens=100,
    )
    if decision is not None:
        logger.debug(
            "女巫结构化决策 save=%s poison=%s reason=%s",
            decision.use_antidote,
            decision.poison_target_id,
            decision.reason,
        )
        return decision

    logger.warning("女巫 LLM 结构化失败，默认本夜不救不毒")
    return WitchNightDecision(use_antidote=False, poison_target_id=POISON_SKIP, reason="")
