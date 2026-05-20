"""
守卫角色处理器（GuardHandler）。

夜晚标准流程（run_night_camp，在狼人刀人之前执行）：
  1. 拼守卫私密 context（上一轮守护、可选目标）
  2. 结构化选择守护目标
  3. 写入 night_actions.guard_protect，并更新 guard_last_protect

规则（标准 12 人局）：
  - 不能守护自己
  - 不能连续两夜守护同一名玩家
  - 仅抵挡狼刀（不能防女巫毒药）
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from utils.helpers import get_guard_protect_candidates, get_players_by_role
from game.models import Role
from llm.night import generate_night_action
from memory.context import build_guard_context
from memory.publish import publish_private

from .base import RoleHandler

if TYPE_CHECKING:
    from game.models import GameState

logger = logging.getLogger("werewolf")


class GuardHandler(RoleHandler):
    """守卫处理器：夜晚守护一名存活玩家（狼刀前行动）。"""

    @property
    def role(self) -> Role:
        return Role.GUARD

    def run_night_camp(self, state: "GameState") -> None:
        guards = get_players_by_role(state, Role.GUARD)
        if not guards:
            return

        guard = guards[0]
        candidates = get_guard_protect_candidates(state, guard.player_id)
        if not candidates:
            logger.info("守卫 %s 号无合法守护目标，跳过今夜守护。", guard.player_id)
            return

        try:
            ctx = build_guard_context(state, guard, candidates)
            target_id = generate_night_action(guard, self.role_key, state, ctx)
        except Exception as e:
            logger.warning("守卫 LLM 行动失败：%s", e)
            target_id = None

        if not self._is_valid_protect_target(state, guard, target_id, candidates):
            target_id = random.choice(candidates)
            logger.info("守卫守护目标无效，随机守护 %s 号", target_id)

        self._record_protect(state, guard, target_id)

    def _is_valid_protect_target(
        self,
        state: "GameState",
        guard,
        target_id: int | None,
        candidates: list[int],
    ) -> bool:
        return target_id is not None and target_id in candidates

    def _record_protect(self, state: "GameState", guard, target_id: int) -> None:
        state.night_actions["guard_protect"] = target_id
        state.guard_last_protect = target_id
        target = state.players[target_id]
        logger.info("守卫 %s 号守护 %s 号", guard.player_id, target_id)
        publish_private(
            state,
            guard.player_id,
            f"你今夜守护了 {target_id} 号（{target.name}）。",
            data_type="action",
        )
