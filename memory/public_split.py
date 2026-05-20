"""公开记忆分桶：system_info 与 speech（5.1 筛选与 5.3 截断共用）。"""
from __future__ import annotations

from typing import List

from .message import Message


def is_system_message(msg: Message) -> bool:
    return msg.data_type == "system_info" or msg.sender == "system"


def split_public_messages(
    messages: List[Message],
) -> tuple[List[Message], List[Message]]:
    system: List[Message] = []
    speech: List[Message] = []
    for msg in messages:
        if msg.data_type == "speech":
            speech.append(msg)
        else:
            system.append(msg)
    return system, speech
