"""
记忆系统生命周期：开局初始化、行动前同步。

init_game_memory：一局只调一次，创建 MsgHub + 每人 PlayerMemory
sync_player_memory：某玩家即将行动前，把 Hub 未读消息拉入其 memory
"""
from typing import TYPE_CHECKING

from game.ledger import record_game_start
from game.models import Role
from .memory import PlayerMemory
from .msg_hub import MsgHub
from .publish import publish_global

if TYPE_CHECKING:
    from game.models import GameState, Player


def init_game_memory(state: "GameState") -> None:
    player_ids = sorted(state.players.keys())
    werewolf_ids = [p.player_id for p in state.players.values() if p.role == Role.WEREWOLF]

    # 每个玩家有独立的 global/private 队列；狼人额外有 werewolf 队列
    state.msg_hub = MsgHub(player_ids, werewolf_ids)
    state.memories = {
        pid: PlayerMemory(pid, state.players[pid].role.value) for pid in player_ids
    }

    alive_desc = "，".join(
        f"{p.player_id}号({p.name})" for p in sorted(state.players.values(), key=lambda x: x.player_id)
    )
    # 开局公告进全员 public 记忆，后续 build_player_context 能读到
    publish_global(state, f"第{state.round}轮游戏开始。在场玩家：{alive_desc}。", data_type="system_info")
    record_game_start(state)


def sync_player_memory(state: "GameState", player: "Player") -> None:
    """从 Hub 拉取该玩家有权看到的全部新消息，追加到三层 memory。"""
    if state.msg_hub is None or player.player_id not in state.memories:
        return
    is_wolf = player.role == Role.WEREWOLF
    batch = state.msg_hub.fetch_all(player.player_id, is_werewolf=is_wolf)
    state.memories[player.player_id].update_from_hub(batch)
