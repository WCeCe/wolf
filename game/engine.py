"""
游戏引擎：三阶段状态机（夜晚 → 白天讨论 → 投票放逐）。

每个 Phase 对应 phases/ 下一个入口函数；各身份的具体流程
由 roles/ 下对应 RoleHandler 实现（狼人频道→刀人、预言家查验等）。

说明：新身份请新增 roles/*.py 并注册到 registry.NIGHT_CAMP_ORDER。
"""
import logging

from game.constants import DEFAULT_MAX_ROUNDS
from utils.helpers import get_alive_players
from game.models import GameState, Phase
from game.phases import day_discussion_phase, night_phase, voting_phase
from game.setup import create_initial_state
from memory.init import init_game_memory
from utils import setup_logger

logger = setup_logger()


def run_one_round(state: GameState) -> None:
    """
    执行一整轮：夜晚 → 白天讨论 → 投票。
    任一阶段内若判定游戏结束，后续阶段会被跳过（phase 已为 GAME_OVER）。
    """
    night_phase(state)
    if state.phase == Phase.GAME_OVER:
        return
    day_discussion_phase(state)
    if state.phase == Phase.GAME_OVER:
        return
    voting_phase(state)


def run_game(max_rounds: int = DEFAULT_MAX_ROUNDS) -> GameState:
    """
    启动 AI 全自动对局。

    1. 创建初始 GameState（12 人标准板子：4 狼 + 4 神 + 4 民）
    2. 初始化 MsgHub + 每人一份 PlayerMemory
    3. 每轮 run_one_round，直到胜负或超过 max_rounds
    """
    from game.constants import PLAYER_COUNT

    state = create_initial_state()
    init_game_memory(state)

    logger.info("===== 狼人杀 AI 对局开始（%s 人）=====", PLAYER_COUNT)
    for pid, p in sorted(state.players.items()):
        logger.info("  %s 号 · %s · %s", pid, p.name, p.role.value)
    logger.info("流程：夜晚 → 白天讨论 → 投票放逐")

    while state.phase != Phase.GAME_OVER:
        # 防止模型/API 异常导致死循环
        if state.round > max_rounds:
            logger.info("达到最大轮数 %s，强制结束。", max_rounds)
            state.phase = Phase.GAME_OVER
            break

        logger.info("\n===== 第 %s 轮 =====", state.round)
        run_one_round(state)

    logger.info("===== 游戏结束 · %s =====", state.phase.value)
    alive = get_alive_players(state)
    if alive:
        logger.info(
            "存活：%s",
            "，".join(f"{p.player_id}号({p.role.value})" for p in alive),
        )
    return state
