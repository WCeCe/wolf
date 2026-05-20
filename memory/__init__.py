"""
memory 包 — 消息 → 记忆 → LLM 上下文（三阶段共用，与 Role 正交）。

数据流：
  三阶段内产生事件 → publish_* → MsgHub
  玩家行动前 → sync → PlayerMemory → build_*_context → llm

详见 docs/PROJECT_STRUCTURE.md §0 概念分层
"""
from .message import Message, Channel
from .msg_hub import MsgHub
from .memory import PlayerMemory
from .init import init_game_memory, sync_player_memory
from .context import (
    build_player_context,
    build_werewolf_channel_context,
    build_wolf_kill_vote_context,
    build_witch_context,
)
from .publish import (
    eliminate_player,
    on_player_eliminated,
    publish_global,
    publish_private,
    publish_werewolf,
)

__all__ = [
    "Message",
    "Channel",
    "MsgHub",
    "PlayerMemory",
    "init_game_memory",
    "sync_player_memory",
    "build_player_context",
    "build_werewolf_channel_context",
    "build_wolf_kill_vote_context",
    "build_witch_context",
    "eliminate_player",
    "on_player_eliminated",
    "publish_global",
    "publish_private",
    "publish_werewolf",
]
