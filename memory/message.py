"""
消息体与频道类型定义。

Hub 按 Channel 决定 fan-out 到哪些玩家的哪条队列；
Memory 按 Channel 归类存入 public / private / werewolf 三层列表。
"""
from enum import Enum
from typing import Any, List, Optional
from datetime import datetime


class Channel(Enum):
    """消息投递频道。"""
    GLOBAL = "global"       # 公开：死讯、发言、投票
    WEREWOLF = "werewolf"   # 狼队私密
    PRIVATE = "private"     # 单人私密（如查验结果）


class Message:
    """单条可投递消息。"""

    def __init__(
        self,
        content: Any,
        sender: str,
        channel: Channel,
        visible_to: Optional[List[int]] = None,
        data_type: str = "speech",
        round: Optional[int] = None,
    ):
        self.timestamp = datetime.now()
        self.content = content
        self.sender = sender            # 玩家编号字符串，或 "system"
        self.channel = channel
        self.visible_to = visible_to
        self.data_type = data_type
        self.round = round
