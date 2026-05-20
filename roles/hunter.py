"""
猎人角色处理器（HunterHandler）。

夜晚无技能。死亡时触发开枪（昨夜狼刀致死或投票放逐）：
  - 整局可开枪一次（hunter_can_shoot）
  - 被女巫救活仍存活 → 不开枪，保留机会
  - 被女巫毒死 → 不能开枪
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, List, Tuple

from utils.helpers import get_hunter_shoot_candidates
from game.ledger import record_hunter_cannot_shoot, record_hunter_shoot
from game.models import Role
from llm.hunter import generate_hunter_shoot
from memory.context import build_hunter_shoot_context
from memory.publish import eliminate_player, publish_global, publish_private

from .base import RoleHandler

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")

# (猎人 id, 被射杀 id)
HunterShoot = Tuple[int, int]

_CANNOT_SHOOT_MSG = {
    "poisoned": "第{round}轮：猎人 {hunter_id} 号被女巫毒死，无法发动开枪技能。",
    "no_targets": "第{round}轮：猎人 {hunter_id} 号出局，但场上已无存活目标，无法开枪。",
    "already_used": "第{round}轮：猎人 {hunter_id} 号出局，但本局开枪技能已使用，无法再次开枪。",
}


class HunterHandler(RoleHandler):
    """猎人：白天/投票同基类；死亡时触发开枪与公布。"""

    @property
    def role(self) -> Role:
        return Role.HUNTER

    def may_shoot(self, state: "GameState", hunter_id: int, cause: str) -> bool:
        """猎人是否仍满足开枪条件。"""
        if hunter_id not in state.players:
            return False
        hunter = state.players[hunter_id]
        if hunter.role != Role.HUNTER:
            return False
        if hunter.is_alive:
            return False
        if not state.hunter_can_shoot:
            return False
        if cause == "night" and state.night_actions.get("witch_poison") == hunter_id:
            return False
        return True

    def resolve_shoots_for_deaths(
        self, state: "GameState", dead_ids: List[int], cause: str
    ) -> List[HunterShoot]:
        """对死亡列表中的猎人依次尝试开枪，返回 (猎人, 目标) 列表。"""
        results: List[HunterShoot] = []

        for pid in dead_ids:
            hunter = state.players[pid]
            if hunter.role != Role.HUNTER:
                continue
            if hunter.is_alive:
                logger.warning("猎人 %s 号仍存活，不应进入死亡开枪流程。", pid)
                continue
            if not self.may_shoot(state, pid, cause):
                if cause == "night" and state.night_actions.get("witch_poison") == pid:
                    state.hunter_can_shoot = False
                    self._announce_cannot_shoot(state, pid, "poisoned")
                    record_hunter_cannot_shoot(state, pid, "poisoned")
                elif not state.hunter_can_shoot:
                    self._announce_cannot_shoot(state, pid, "already_used")
                    record_hunter_cannot_shoot(state, pid, "already_used")
                continue

            target_id = self.shoot_on_death(state, hunter, cause)
            if target_id is not None:
                results.append((pid, target_id))

        return results

    def announce_shoots(self, state: "GameState", shoots: List[HunterShoot]) -> None:
        """公布猎人开枪结果（不公开被射杀者身份）。"""
        for hunter_id, target_id in shoots:
            target = state.players[target_id]
            msg = (
                f"第{state.round}轮：猎人 {hunter_id} 号开枪带走 "
                f"{target_id} 号玩家（不公布其身份）。"
            )
            state.public_log.append(msg)
            publish_global(state, msg, data_type="system_info")
            record_hunter_shoot(state, hunter_id, target_id)
            logger.info(
                "猎人 %s 号开枪带走 %s 号（%s）。",
                hunter_id,
                target_id,
                target.role.value,
            )

    def shoot_on_death(
        self, state: "GameState", hunter: "Player", cause: str
    ) -> int | None:
        """猎人出局时开枪；成功返回目标 id 并已击杀，否则 None。"""
        if not self.may_shoot(state, hunter.player_id, cause):
            logger.warning(
                "猎人 %s 号 shoot_on_death 未通过 may_shoot 校验，跳过。",
                hunter.player_id,
            )
            return None

        candidates = get_hunter_shoot_candidates(state)
        if not candidates:
            state.hunter_can_shoot = False
            self._announce_cannot_shoot(state, hunter.player_id, "no_targets")
            logger.info("猎人 %s 号开枪时场上无存活目标。", hunter.player_id)
            return None

        ctx = build_hunter_shoot_context(state, hunter, cause)
        try:
            target_id = generate_hunter_shoot(hunter, state, ctx, cause)
        except Exception as e:
            logger.warning("猎人 %s 开枪 LLM 失败：%s", hunter.name, e)
            target_id = None

        if target_id is None or target_id not in candidates:
            target_id = random.choice(candidates)
            logger.warning(
                "猎人 %s 开枪目标无效，随机射杀 %s 号", hunter.name, target_id
            )

        victim = state.players[target_id]
        eliminate_player(state, target_id)
        state.hunter_can_shoot = False
        if cause == "night":
            state.night_actions["hunter_shot"] = target_id

        cause_label = "被投票放逐" if cause == "vote" else "昨夜死亡"
        publish_private(
            state,
            hunter.player_id,
            f"你因{cause_label}发动猎人技能，开枪带走了 {target_id} 号（{victim.role.value}）。",
            sender=str(hunter.player_id),
            data_type="action",
        )
        logger.debug(
            "猎人 %s 开枪 target_id=%s cause=%s", hunter.name, target_id, cause
        )
        return target_id

    def _announce_cannot_shoot(
        self, state: "GameState", hunter_id: int, reason: str
    ) -> None:
        template = _CANNOT_SHOOT_MSG.get(reason)
        if template is None:
            return
        msg = template.format(round=state.round, hunter_id=hunter_id)
        state.public_log.append(msg)
        publish_global(state, msg, data_type="system_info")
        logger.info(msg)
