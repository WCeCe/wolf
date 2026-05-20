"""
预言家角色处理器（SeerHandler）。

夜晚标准流程（run_night_camp）：
  1. 拼预言家私密 context（强调每夜仅可查验一人）
  2. 结构化选择查验目标（仅调用一次 LLM 决策链）
  3. 写入 night_actions.seer_check，并向预言家发布私密查验结果

规则：每夜只能查验一名存活玩家（不能查自己）；本夜已查验则不再执行。
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from utils.helpers import get_players_by_role, get_seer_check_candidates
from game.models import Role
from llm.night import generate_night_action
from memory.context import build_seer_context
from memory.publish import publish_private

from .base import RoleHandler

if TYPE_CHECKING:
    from game.models import GameState

logger = logging.getLogger("werewolf")


class SeerHandler(RoleHandler):
    """预言家处理器：每夜至多查验一名存活玩家。"""

    @property
    def role(self) -> Role:
        return Role.SEER

    def run_night_camp(self, state: "GameState") -> None:
        seers = get_players_by_role(state, Role.SEER)
        if not seers:
            return

        if state.night_actions.get("seer_check") is not None:
            logger.warning("本夜预言家查验已执行，跳过重复调用。")
            return

        seer = seers[0]
        candidates = get_seer_check_candidates(state, seer.player_id)
        if not candidates:
            logger.info("预言家 %s 号无合法查验目标，跳过。", seer.player_id)
            return

        target_id: int | None = None
        try:
            ctx = build_seer_context(state, seer)
            target_id = generate_night_action(seer, self.role_key, state, ctx)
        except Exception as e:
            logger.warning("预言家 LLM 行动失败：%s", e)

        if self._is_valid_check_target(state, seer, target_id, candidates):
            self._record_check(state, seer, target_id, source="llm")
            return

        if state.night_actions.get("seer_check") is not None:
            return

        tid = random.choice(candidates)
        self._record_check(state, seer, tid, source="fallback")
        logger.info("预言家查验无效，随机查验 %s 号", tid)

    def _is_valid_check_target(
        self,
        state: "GameState",
        seer,
        target_id: int | None,
        candidates: list[int],
    ) -> bool:
        if target_id is None or target_id not in candidates:
            return False
        target = state.players[target_id]
        return target.is_alive and target_id != seer.player_id

    def _record_check(
        self,
        state: "GameState",
        seer,
        target_id: int,
        *,
        source: str = "llm",
    ) -> None:
        if state.night_actions.get("seer_check") is not None:
            logger.warning("预言家本夜已查验，忽略重复记录（source=%s）。", source)
            return

        checked = state.players[target_id]
        state.night_actions["seer_check"] = (target_id, checked.role.value)
        state.seer_check_history.append((target_id, checked.role.value))
        logger.info("预言家查验 %s 号 → 身份：%s", target_id, checked.role.value)
        publish_private(
            state,
            seer.player_id,
            f"你查验了 {target_id} 号，身份是：{checked.role.value}",
            data_type="action",
        )
