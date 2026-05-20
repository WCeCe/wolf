"""
游戏内 Role 枚举与 LLM 配置键的映射。

config/llm_config.yaml 和 prompts 目录使用英文键（werewolf / seer 等），
本模块负责在调用 LLM 前把 Player.role 转成对应字符串。
"""
from .models import Player, Role

# 标准 12 人局人数（4 狼 + 4 神 + 4 民）
PLAYER_COUNT = 12

# 防止模型/API 异常导致死循环时的安全上限（与 engine.run_game 一致）
DEFAULT_MAX_ROUNDS = 40

ROLE_KEY = {
    Role.WEREWOLF: "werewolf",
    Role.SEER: "seer",
    Role.WITCH: "witch",
    Role.VILLAGER: "villager",
    Role.HUNTER: "hunter",
    Role.GUARD: "guard",
}

# 好人阵营身份集合，供 rules.check_game_over 等复用
GOOD_ROLES = frozenset({Role.VILLAGER, Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD})

# 神职（12 人标准局四神）
GOD_ROLES = frozenset({Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD})


def role_key(player: Player) -> str:
    """返回该玩家对应的 LLM 配置 / prompt 角色名。"""
    return ROLE_KEY[player.role]
