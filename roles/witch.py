"""
女巫角色处理器（WitchHandler）。

夜晚标准流程（run_night_camp）：
  1. 读取今夜狼刀 night_actions.wolf_kill
  2. 拼女巫私密 context（刀口、药水存量）
  3. 结构化决定解药 / 毒药
  4. 写入 night_actions.witch_save / witch_poison，并更新药水状态

规则（标准 12 人局）：
  - 解药、毒药各一瓶，整局各用一次
  - 解药仅能救今夜狼刀目标
  - 毒药可毒任意存活玩家（不含女巫自己）
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from utils.helpers import get_alive_players, get_players_by_role
from game.models import Role
from llm.witch import generate_witch_night_action
from memory.context import build_witch_context
from memory.god_consolidation import append_witch_potion_log
from memory.publish import publish_private
from schemas.witch_action import POISON_SKIP

from .base import RoleHandler

if TYPE_CHECKING:
    from game.models import GameState

logger = logging.getLogger("werewolf")


class WitchHandler(RoleHandler):
    """女巫处理器：在狼刀之后决定救/毒。"""

    @property
    def role(self) -> Role:
        return Role.WITCH

    def run_night_camp(self, state: "GameState") -> None:
        witches = get_players_by_role(state, Role.WITCH)
        if not witches:
            return

        witch = witches[0]
        wolf_kill_id = state.night_actions.get("wolf_kill")
        can_use_antidote = state.witch_has_antidote and wolf_kill_id is not None

        # 毒药目标：存活且非女巫本人（与 llm 层 poison_candidates 约定一致）
        poison_candidates = [
            p.player_id for p in get_alive_players(state) if p.player_id != witch.player_id
        ]

        try:
            ctx = build_witch_context(
                state,
                witch,
                wolf_kill_id=wolf_kill_id,
                can_use_antidote=can_use_antidote,
                can_use_poison=state.witch_has_poison,
            )
            decision = generate_witch_night_action(
                witch,
                state,
                ctx,
                can_use_antidote=can_use_antidote,
                wolf_kill_id=wolf_kill_id,
                poison_candidates=poison_candidates if state.witch_has_poison else [],
            )
        except Exception as e:
            logger.warning("女巫 LLM 行动失败：%s", e)
            decision = None

        use_antidote = False
        poison_target: int | None = None

        if decision is not None:
            use_antidote = decision.use_antidote and can_use_antidote
            if (
                state.witch_has_poison
                and decision.poison_target_id != POISON_SKIP
                and decision.poison_target_id in poison_candidates
            ):
                poison_target = decision.poison_target_id

        state.night_actions["witch_save"] = use_antidote
        state.night_actions["witch_poison"] = poison_target

        append_witch_potion_log(
            state,
            round_num=state.round,
            used_antidote=use_antidote,
            wolf_kill_id=wolf_kill_id,
            poison_target=poison_target,
            had_antidote_choice=can_use_antidote,
            had_poison_choice=state.witch_has_poison,
        )

        if use_antidote:
            state.witch_has_antidote = False
            publish_private(
                state,
                witch.player_id,
                f"你使用解药救活了 {wolf_kill_id} 号（狼人刀口）。",
                data_type="action",
            )
            logger.info("女巫使用解药救活 %s 号", wolf_kill_id)
        elif can_use_antidote:
            publish_private(state, witch.player_id, "你选择不使用解药。", data_type="action")

        if poison_target is not None:
            state.witch_has_poison = False
            publish_private(
                state,
                witch.player_id,
                f"你使用毒药毒杀了 {poison_target} 号。",
                data_type="action",
            )
            logger.info("女巫使用毒药毒杀 %s 号", poison_target)
        elif state.witch_has_poison:
            publish_private(state, witch.player_id, "你选择不使用毒药。", data_type="action")
