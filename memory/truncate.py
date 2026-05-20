"""
5.3 分类型通道截断：按消息类型分桶，超 cap 时保留最新条目。
"""
from __future__ import annotations

from typing import List

from game.models import Role

from .message import Message
from .public_split import split_public_messages
from .policy_config import (
    PUBLIC_SPEECH_CAP,
    PUBLIC_SYSTEM_CAP,
    private_cap_for,
    werewolf_cap_for,
)


def _tail_keep_newest(messages: List[Message], cap: int) -> List[Message]:
    if cap <= 0:
        return []
    if len(messages) <= cap:
        return list(messages)
    return list(messages[-cap:])


def truncate_public_memory(messages: List[Message]) -> List[Message]:
    system, speech = split_public_messages(messages)
    system = _tail_keep_newest(system, PUBLIC_SYSTEM_CAP)
    speech = _tail_keep_newest(speech, PUBLIC_SPEECH_CAP)
    return system + speech


def truncate_private_memory(messages: List[Message], role: Role) -> List[Message]:
    return _tail_keep_newest(messages, private_cap_for(role))


def truncate_werewolf_memory(messages: List[Message], role: Role) -> List[Message]:
    cap = werewolf_cap_for(role)
    if cap <= 0:
        return list(messages)
    return _tail_keep_newest(messages, cap)


def truncate_player_memory(
    *,
    role: Role,
    public_memory: List[Message],
    private_memory: List[Message],
    werewolf_memory: List[Message],
) -> tuple[List[Message], List[Message], List[Message]]:
    """对三层记忆应用 5.3 分类型上限。"""
    return (
        truncate_public_memory(public_memory),
        truncate_private_memory(private_memory, role),
        truncate_werewolf_memory(werewolf_memory, role),
    )
