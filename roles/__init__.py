"""
角色处理器包（roles/）。

每个身份一套标准流程（沟通、刀人、查验、救毒、发言、投票）
"""
from .base import RoleHandler
from .registry import NIGHT_CAMP_ORDER, get_player_handler, get_role_handler, run_night_camps
from .guard import GuardHandler
from .hunter import HunterHandler
from .seer import SeerHandler
from .villager import VillagerHandler
from .werewolf import WerewolfHandler
from .witch import WitchHandler

__all__ = [
    "RoleHandler",
    "WerewolfHandler",
    "SeerHandler",
    "WitchHandler",
    "VillagerHandler",
    "HunterHandler",
    "GuardHandler",
    "get_role_handler",
    "get_player_handler",
    "run_night_camps",
    "NIGHT_CAMP_ORDER",
]
