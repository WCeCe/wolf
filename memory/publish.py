"""
游戏事件发布入口（引擎侧写消息请只调本文件三个函数）。

事件发生后 → broadcast 进 MsgHub → 玩家行动前 sync 进 PlayerMemory → 拼进 LLM context
"""
import logging
from typing import TYPE_CHECKING

from game.models import Role
from .message import Channel, Message

logger = logging.getLogger("werewolf")

if TYPE_CHECKING:
    from game.models import GameState


def on_player_eliminated(state: "GameState", player_id: int) -> None:
    """
    玩家出局后的 Hub 收束（不改 is_alive，由 eliminate_player 或等价逻辑负责）。

    死狼移出 werewolf_ids，避免狼队频道仍向死者广播。
    """
    if state.msg_hub is None:
        return
    player = state.players.get(player_id)
    if player is not None and player.role == Role.WEREWOLF:
        state.msg_hub.remove_werewolf(player_id)


def eliminate_player(state: "GameState", player_id: int) -> bool:
    """
    标记玩家死亡并收束 Hub。

    返回 True 表示本调用 newly eliminated；已死亡则 False。
    """
    player = state.players.get(player_id)
    if player is None or not player.is_alive:
        return False
    player.is_alive = False
    on_player_eliminated(state, player_id)
    return True


def _round_of(state: "GameState") -> int:
    return state.round


def publish_global(
    state: "GameState",
    content: str,
    sender: str = "system",
    data_type: str = "system_info",
) -> None:
    """全员可见：死讯、发言、投票结果等 → 每人 global 队列各一份。"""
    if state.msg_hub is None:
        return
    state.msg_hub.broadcast(
        Message(
            content,
            sender,
            Channel.GLOBAL,
            data_type=data_type,
            round=_round_of(state),
        )
    )


def publish_private(
    state: "GameState",
    player_id: int,
    content: str,
    sender: str = "system",
    data_type: str = "system_info",
) -> None:
    """仅指定 player_id 可见：预言家查验等 → 该玩家 private 队列。"""
    if state.msg_hub is None:
        return
    state.msg_hub.broadcast(
        Message(
            content,
            sender,
            Channel.PRIVATE,
            visible_to=[player_id],
            data_type=data_type,
            round=_round_of(state),
        )
    )


def publish_werewolf(
    state: "GameState",
    content: str,
    sender: str,
    data_type: str = "action",
) -> None:
    """仅狼人可见：狼队交流、刀口 → 各狼 werewolf 队列；并额外写 game.log。"""
    if state.msg_hub is None:
        return
    state.msg_hub.broadcast(
        Message(
            content,
            sender,
            Channel.WEREWOLF,
            data_type=data_type,
            round=_round_of(state),
        )
    )

    wolf_ids = sorted(state.msg_hub.werewolf_ids)
    audience = "、".join(f"{pid}号" for pid in wolf_ids) if wolf_ids else "无"
    logger.info(
        "[狼队频道] %s号 → %s | 存活狼可见: %s | type=%s",
        sender,
        content,
        audience,
        data_type,
    )
