"""
游戏三阶段入口（与 Phase 枚举一一对应）。

  night_phase             → Phase.NIGHT（内含狼人/预言家/女巫等角色活动）
  day_discussion_phase    → Phase.DAY_DISCUSSION
  voting_phase            → Phase.VOTING
"""
from .day import day_discussion_phase
from .night import night_phase
from .voting import voting_phase

__all__ = ["night_phase", "day_discussion_phase", "voting_phase"]
