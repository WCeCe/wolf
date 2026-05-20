"""
角色处理器注册表。

引擎通过本模块获取各身份的 Handler 实例，避免在 phases 里散落 if/else。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from utils.helpers import get_players_by_role
from game.models import Role

from .base import RoleHandler
from .guard import GuardHandler
from .hunter import HunterHandler
from .seer import SeerHandler
from .villager import VillagerHandler
from .werewolf import WerewolfHandler
from .witch import WitchHandler

if TYPE_CHECKING:
    from game.models import GameState, Player

# 单例 Handler 实例（无状态，可复用）
_HANDLERS: dict[Role, RoleHandler] = {
    Role.WEREWOLF: WerewolfHandler(),
    Role.SEER: SeerHandler(),
    Role.WITCH: WitchHandler(),
    Role.VILLAGER: VillagerHandler(),
    Role.HUNTER: HunterHandler(),
    Role.GUARD: GuardHandler(),
}

# 夜晚阵营活动执行顺序（村民/猎人无夜晚技能，不在此列）
# 守卫在狼人刀人之前行动，且不知晓刀口
NIGHT_CAMP_ORDER: tuple[Role, ...] = (
    Role.GUARD,
    Role.WEREWOLF,
    Role.SEER,
    Role.WITCH,
)


def get_role_handler(role: Role) -> RoleHandler:
    """按身份枚举返回对应 Handler；未知身份回退为村民 Handler。"""
    return _HANDLERS.get(role, _HANDLERS[Role.VILLAGER])


def get_player_handler(player: "Player") -> RoleHandler:
    """按玩家当前身份返回 Handler（用于白天发言、投票等按人调用）。"""
    return get_role_handler(player.role)


def run_night_camps(state: "GameState") -> None:
    """
    依次执行有夜晚技能的阵营流程。

    仅当场上仍存在该身份存活玩家时才调用对应 Handler.run_night_camp。
    """
    for role in NIGHT_CAMP_ORDER:
        if get_players_by_role(state, role):
            get_role_handler(role).run_night_camp(state)


def resolve_hunter_shoots_for_deaths(
    state: "GameState", dead_ids: list[int], cause: str
) -> list:
    """死亡列表中的猎人依次开枪（昨夜或投票）。"""
    handler = get_role_handler(Role.HUNTER)
    assert isinstance(handler, HunterHandler)
    return handler.resolve_shoots_for_deaths(state, dead_ids, cause)


def announce_hunter_shoots(state: "GameState", shoots: list) -> None:
    """公布猎人开枪结果。"""
    handler = get_role_handler(Role.HUNTER)
    assert isinstance(handler, HunterHandler)
    handler.announce_shoots(state, shoots)
