"""
多人对局历史的 LLM 格式化。

问题：多条发言若不带说话人标签，模型容易混淆「谁说了什么」、甚至误认自己的座位号。
做法：统一「{座位号}号: 内容」并包在 <history> 里，与当前回合指令区分开。

与 DashScope MultiAgentFormatter 思路相同，为本项目定制的轻量实现。
"""
from __future__ import annotations

from typing import Iterable

from .message import Message


def format_speaker(sender: str, *, werewolf_channel: bool = False) -> str:
    """
    将 Message.sender 转为模型可读的发言者标签。

    - system → 系统
    - 玩家编号 → 3号 或 3号狼队友（狼队频道）
    """
    if sender == "system":
        return "系统"
    if werewolf_channel:
        return f"{sender}号狼队友"
    return f"{sender}号"


def format_message_line(msg: Message, *, werewolf_channel: bool = False) -> str:
    """单条消息 → 「3号: 发言内容」。"""
    speaker = format_speaker(msg.sender, werewolf_channel=werewolf_channel)
    return f"{speaker}: {msg.content}"


def wrap_history(lines: Iterable[str]) -> str:
    """
    将多行发言包进 <history>，便于模型区分「过往记录」与「当前要你做的事」。

    空列表返回空字符串。
    """
    body = "\n".join(lines)
    if not body:
        return ""
    return f"<history>\n{body}\n</history>"


def format_message_block(
    messages: list[Message],
    *,
    werewolf_channel: bool = False,
    system_as_announcement: bool = True,
) -> str:
    """
    把一组 Message 格式化为带 <history> 的文本块。

    system_info 或 sender=system 的消息标为「系统:」，其余按座位号标注。
    """
    lines: list[str] = []
    for msg in messages:
        if system_as_announcement and (
            msg.data_type == "system_info" or msg.sender == "system"
        ):
            lines.append(f"系统: {msg.content}")
        else:
            lines.append(format_message_line(msg, werewolf_channel=werewolf_channel))
    return wrap_history(lines)
