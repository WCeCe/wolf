"""
游戏核心数据模型。

本文件只定义「状态长什么样」，不包含任何流程逻辑。
引擎（engine / phases）读写 GameState；记忆系统挂在 msg_hub / memories 上。
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, TypedDict

from game.ledger import RoundLedger


class NightActionRecord(TypedDict, total=False):
    """
    单夜各阵营写入的结构化决策（夜晚不扣血，白天再结算）。

    键由对应 RoleHandler 写入；见 docs/PROJECT_STRUCTURE.md。
    """
    wolf_kill: int
    seer_check: Tuple[int, str]
    witch_save: bool
    witch_poison: int | None
    guard_protect: int
    hunter_shot: int


class Role(Enum):
    """玩家身份（中文 value 用于日志与记忆展示）。"""
    WEREWOLF = "狼人"
    VILLAGER = "村民"
    SEER = "预言家"
    WITCH = "女巫"
    HUNTER = "猎人"
    GUARD = "守卫"


class Phase(Enum):
    """
    游戏阶段（仅三档常规流程 + 终局）。

    狼人刀人、预言家查验、女巫用药等是 NIGHT 内的角色活动，不是独立 Phase。
    """
    NIGHT = "夜晚"
    DAY_DISCUSSION = "白天讨论"
    VOTING = "投票"
    GAME_OVER = "游戏结束"


@dataclass
class Player:
    """单个玩家的运行时状态。"""
    player_id: int          # 座位号，1~12（见 constants.PLAYER_COUNT）
    name: str               # 显示名，如「玩家1」
    role: Role              # 本局身份（开局后不变）
    is_alive: bool = True   # False 表示已死亡或已被放逐


@dataclass
class GameState:
    """整局游戏的唯一状态快照，所有阶段函数都读写同一个实例。"""
    players: Dict[int, Player] = field(default_factory=dict)
    phase: Phase = Phase.NIGHT
    round: int = 1  # 当前轮次，投票结束后 +1

    # 夜晚暂存区：白天才开始结算死亡，避免「刀了但女巫还能救」时序错乱
    night_actions: NightActionRecord = field(default_factory=dict)

    # 守卫上一轮守护目标（None 表示首夜；不能连续两夜守护同一人）
    guard_last_protect: int | None = None

    # 预言家历史查验：(座位号, 身份中文)，用于私密上下文；每夜仍只能新增一次
    seer_check_history: List[Tuple[int, str]] = field(default_factory=list)

    # 猎人是否仍可开枪（整局一次；被女巫救活不消耗；毒死或开枪后变为 False）
    hunter_can_shoot: bool = True

    # 女巫药水（整局各一瓶）
    witch_has_antidote: bool = True
    witch_has_poison: bool = True
    # 5.7 女巫用药紧凑账本（每夜一行，替代 private 叙述送入 LLM）
    witch_potion_log: List[str] = field(default_factory=list)

    vote_results: Dict[int, int] = field(default_factory=dict)  # 投票者 id → 被投 id

    # 5.2 局面账本（规则生成，全员共享；远轮要点供 memory 出库）
    round_ledger: RoundLedger = field(default_factory=RoundLedger)

    # 是否已进行过至少一次完整白天公聊（首轮 night 后为 False，day 结束后 True）
    day_discussion_occurred: bool = False

    # 以下仅供日志/调试；LLM 上下文走 MsgHub → PlayerMemory（见 memory/）
    discussion_log: List[str] = field(default_factory=list)
    public_log: List[str] = field(default_factory=list)

    # 记忆系统（run_game 里 init_game_memory 后才有值）
    msg_hub: Any = None                       # MsgHub 实例
    memories: Dict[int, Any] = field(default_factory=dict)  # player_id → PlayerMemory
