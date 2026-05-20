"""
开局设置：创建 12 人标准板子的初始 GameState。

身份分配（饭局/网易常见 12 人标准）：
  - 4 狼人
  - 4 神职：预言家、女巫、猎人、守卫
  - 4 村民
开局前随机洗牌座位，保证公平性。
"""
import random

from .constants import PLAYER_COUNT
from .models import GameState, Player, Role

# 标准 12 人局身份池（洗牌前固定构成）
_STANDARD_ROLES: list[Role] = (
    [Role.WEREWOLF] * 4
    + [Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD]
    + [Role.VILLAGER] * 4
)

assert len(_STANDARD_ROLES) == PLAYER_COUNT, (
    f"身份池数量 {len(_STANDARD_ROLES)} 与 PLAYER_COUNT {PLAYER_COUNT} 不一致"
)


def create_initial_state() -> GameState:
    """创建初始状态：随机分配 1~12 号座位上的身份。"""
    state = GameState()
    roles = list(_STANDARD_ROLES)
    random.shuffle(roles)
    for i, role in enumerate(roles):
        state.players[i + 1] = Player(player_id=i + 1, name=f"玩家{i + 1}", role=role)
    return state
