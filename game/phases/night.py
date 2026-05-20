"""
阶段一：夜晚（Phase.NIGHT）。

本文件只负责阶段壳：清空 night_actions、按顺序调度各角色 Handler 的夜晚流程。
具体逻辑见 roles/（狼人：频道→刀人；预言家：查验；女巫：救/毒）。

夜晚只记录 night_actions，不扣血；死亡在白天讨论开头结算。
"""
import logging

from game.models import GameState, Phase
from roles.registry import run_night_camps

logger = logging.getLogger("werewolf")


def night_phase(state: GameState) -> None:
    logger.info("=== 夜晚 ===")
    state.phase = Phase.NIGHT
    state.night_actions = {}

    # 按 NIGHT_CAMP_ORDER 依次调用各阵营 Handler.run_night_camp
    run_night_camps(state)

    state.phase = Phase.DAY_DISCUSSION
