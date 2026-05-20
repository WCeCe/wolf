"""
夜晚行动结算：在白天公布死讯时调用。

死亡来源：
  1. 狼刀目标（除非被女巫解药救活，或被守卫守护；猎人被救下则不开枪且保留开枪机会）
  2. 女巫毒药目标（守卫无法防毒；可与狼刀为同一人：先判定狼刀，再判定毒药）

公开信息：仅公布是否有人死亡；狼刀指向谁、是否被守卫抵挡或女巫救活，不向全场公开
（女巫若用解药则仅女巫知晓刀口）。
"""
from typing import List, Optional

from game.models import GameState
from memory.publish import eliminate_player


def wolf_kill_blocked_by(state: GameState) -> Optional[str]:
    """
    若本夜有狼刀但未造成死亡，返回抵挡原因：guard / witch_save；否则 None。

    仅供引擎日志与调试，不写入 public_log。
    """
    wolf_kill_id = state.night_actions.get("wolf_kill")
    if wolf_kill_id is None or wolf_kill_id not in state.players:
        return None
    victim = state.players[wolf_kill_id]
    if not victim.is_alive:
        return None
    if state.night_actions.get("witch_save"):
        return "witch_save"
    if state.night_actions.get("guard_protect") == wolf_kill_id:
        return "guard"
    return None


def resolve_night_deaths(state: GameState) -> List[int]:
    """
    根据 night_actions 结算昨夜死亡并修改 is_alive。
    返回昨夜死亡玩家 id 列表（去重、升序）。
    """
    deaths: List[int] = []
    wolf_kill_id = state.night_actions.get("wolf_kill")
    witch_saved = state.night_actions.get("witch_save", False)
    guard_protect_id = state.night_actions.get("guard_protect")
    poison_id = state.night_actions.get("witch_poison")

    if wolf_kill_id is not None and wolf_kill_id in state.players:
        victim = state.players[wolf_kill_id]
        guarded = guard_protect_id == wolf_kill_id
        if victim.is_alive and not witch_saved and not guarded:
            if eliminate_player(state, wolf_kill_id):
                deaths.append(wolf_kill_id)

    if poison_id is not None and poison_id in state.players:
        if eliminate_player(state, poison_id) and poison_id not in deaths:
            deaths.append(poison_id)

    return sorted(deaths)
