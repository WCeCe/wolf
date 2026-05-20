"""
夜晚结构化行动：狼刀、预言家查验等需要「确定目标编号」的场景。

输出约定：JSON { "target_id": int, "reason": str }
调用链：generate_night_action → call_structured_completion → schemas.night_action 解析

失败回退顺序：
  1. response_format=json_schema (strict)，传输失败每格式最多重试 2 次
  2. response_format=json_object，同上
  3. 自由文本 + 正则提取合法 target_id（传输亦最多 2 次）
  仍失败则返回 None，由 roles 层随机兜底
"""
import logging
from typing import TYPE_CHECKING, Optional

from schemas.night_action import (
    NightTargetDecision,
    build_night_target_json_schema,
    parse_night_target_decision,
)

from utils.helpers import (
    get_guard_protect_candidates,
    get_killable_ids,
    get_seer_check_candidates,
)
from config.loader import PROMPT_TIER_COMPACT
from llm.client import generate_player_response, loader
from llm.prompt_format import build_user_message
from llm.structured import call_structured_completion, extract_target_id_from_text

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")


def _night_action_user_message(
    player_id: int,
    player_name: str,
    role_key: str,
    context: str,
    round_num: int,
    candidates: list[int],
    action_label: str,
) -> str:
    """在 night.yaml 行动指令上追加「必须输出 JSON」的硬性约束。"""
    action_prompt = loader.load_action_prompt("night", role_key)
    task_part = loader.render_prompt(
        action_prompt,
        player_id=player_id,
        player_name=player_name,
        round=round_num,
    )
    body = build_user_message(task_part, context)
    return (
        f"{body}\n\n"
        f"【结构化输出】{action_label}。target_id 必须是以下之一：{candidates}。\n"
        f"请输出 JSON 对象，包含字段 target_id（整数）、reason（字符串）。"
    )


def generate_night_action(
    player: "Player",
    role_key: str,
    state: "GameState",
    context: str | None = None,
) -> Optional[int]:
    """
    夜晚行动入口，成功时返回目标 player_id，失败返回 None。

    根据 role_key 计算合法 candidates（见 utils.helpers）。
    """
    if role_key == "werewolf":
        candidates = get_killable_ids(state)
        action_label = "选择击杀目标"
    elif role_key == "seer":
        candidates = get_seer_check_candidates(state, player.player_id)
        action_label = "选择查验目标"
    elif role_key == "guard":
        candidates = get_guard_protect_candidates(state, player.player_id)
        action_label = "选择守护目标"
    else:
        from utils.helpers import get_alive_player_ids

        candidates = get_alive_player_ids(state)
        action_label = "选择行动目标"

    if not candidates:
        return None

    if context is None:
        context = f"当前第{state.round}轮夜晚。"

    cfg = loader.load_llm_config(role_key)
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = loader.load_system_prompt(role_key, PROMPT_TIER_COMPACT)
    user_message = _night_action_user_message(
        player.player_id,
        player.name,
        role_key,
        context,
        state.round,
        candidates,
        action_label,
    )

    schema = build_night_target_json_schema(candidates)

    def _parse(raw: str) -> NightTargetDecision | None:
        return parse_night_target_decision(raw, candidates)

    decision = call_structured_completion(
        cfg,
        system_prompt,
        user_message,
        schema_name="night_target_decision",
        json_schema=schema,
        parse_raw=_parse,
    )
    if decision is not None:
        logger.debug(
            "%s 夜晚结构化决策 target_id=%s reason=%s",
            player.name,
            decision.target_id,
            decision.reason,
        )
        return decision.target_id

    # 最后一级：当普通 night phase 文本生成，再正则解析
    logger.warning("%s 结构化夜晚行动失败，尝试自由文本兜底", player.name)
    raw = generate_player_response(
        player.name,
        role_key,
        "night",
        user_message,
        state.round,
        player_id=player.player_id,
    )
    return extract_target_id_from_text(raw, candidates)
