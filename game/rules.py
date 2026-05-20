"""
胜负判定规则。

好人阵营 = 村民 + 预言家 + 女巫 + 猎人（见 constants.GOOD_ROLES）。
结束条件：
  - 狼人全灭 → 好人胜
  - 存活狼人数 >= 存活好人数 → 狼人胜
"""
import logging

from .constants import GOOD_ROLES
from utils.helpers import get_alive_players
from .models import GameState, Phase, Role

logger = logging.getLogger("werewolf")


def check_game_over(state: GameState) -> bool:
    alive = get_alive_players(state)
    wolves = [p for p in alive if p.role == Role.WEREWOLF]
    goods = [p for p in alive if p.role in GOOD_ROLES]

    if not wolves:
        logger.info("所有狼人出局，好人阵营获胜！")
        state.phase = Phase.GAME_OVER
        return True
    if len(wolves) >= len(goods):
        logger.info("狼人阵营人数不少于好人阵营，狼人获胜！")
        state.phase = Phase.GAME_OVER
        return True
    return False
