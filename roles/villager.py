"""
村民角色处理器（VillagerHandler）。

夜晚无阵营行动（继承基类空 run_night_camp）。
白天讨论与投票使用基类标准流程，策略差异由 config/prompts 中 villager 的 prompt 定义。
"""
from game.models import Role

from .base import RoleHandler


class VillagerHandler(RoleHandler):
    """村民处理器：夜晚 no-op；白天/投票走基类默认实现。"""

    @property
    def role(self) -> Role:
        return Role.VILLAGER
