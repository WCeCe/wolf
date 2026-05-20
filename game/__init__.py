"""
游戏核心包：状态模型、规则、阶段流程、对局编排。

注意：不在包初始化时 import engine，避免 game → phases → roles → game 循环依赖。
请使用 from game import run_game 或 from game.engine import run_game。
"""
from .constants import DEFAULT_MAX_ROUNDS, GOD_ROLES, GOOD_ROLES, PLAYER_COUNT
from .models import GameState, Phase, Player, Role
from .setup import create_initial_state


def run_one_round(state: GameState) -> None:
    from .engine import run_one_round as _run_one_round

    return _run_one_round(state)


def run_game(max_rounds: int = DEFAULT_MAX_ROUNDS) -> GameState:
    from .engine import run_game as _run_game

    return _run_game(max_rounds)


__all__ = [
    "Role",
    "Phase",
    "Player",
    "GameState",
    "PLAYER_COUNT",
    "DEFAULT_MAX_ROUNDS",
    "GOOD_ROLES",
    "GOD_ROLES",
    "create_initial_state",
    "run_one_round",
    "run_game",
]
