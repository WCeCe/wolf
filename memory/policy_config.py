"""记忆策略常量：5.1 出库窗口、5.3 分类型通道上限。"""

from game.models import Role

# --- 5.1 出库 ---
SPEECH_ROUNDS_DISCUSS = 2
SPEECH_ROUNDS_LAST_WORDS = 2
SPEECH_ROUNDS_VOTE = 1
SPEECH_ROUNDS_HUNTER_SHOOT = 2
WOLF_SYSTEM_LAST_N = 10

# --- 5.3 全员 public（不按角色）---
PUBLIC_SPEECH_CAP = 36
PUBLIC_SYSTEM_CAP = 80

# --- 5.3 按角色的 private / werewolf ---
CHANNEL_CAPS: dict[Role, dict[str, int]] = {
    Role.WEREWOLF: {"private": 20, "werewolf": 64},
    Role.SEER: {"private": 40},
    Role.WITCH: {"private": 30},
    Role.GUARD: {"private": 20},
    Role.HUNTER: {"private": 10},
    Role.VILLAGER: {"private": 10},
}

DEFAULT_PRIVATE_CAP = 10


def private_cap_for(role: Role) -> int:
    return CHANNEL_CAPS.get(role, {}).get("private", DEFAULT_PRIVATE_CAP)


def werewolf_cap_for(role: Role) -> int:
    return CHANNEL_CAPS.get(role, {}).get("werewolf", 0)
