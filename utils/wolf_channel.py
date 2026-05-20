"""狼队私密频道：发言顺序提示与协商文案（供 roles/werewolf 使用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from game.models import Player

ChannelLine = tuple[int, str]


def build_channel_speak_hint(
    *,
    speak_index: int,
    wolf_count: int,
    channel_lines: List[ChannelLine],
    killable_ids: List[int],
) -> str:
    """
    按发言顺位注入不同战术要求，减少全员「同意刀X」。

    speak_index: 0 为首麦，1..n-1 为跟麦。
    """
    if speak_index == 0:
        return (
            f"【频道角色：首麦（{speak_index + 1}/{wolf_count}）】"
            "请主动提出刀口方案：必须写「刀X号」+ 一句独立战术理由"
            "（如抗推位、神职风险、与队友配合）。不要只抛开放式问题。"
        )

    prior = "\n".join(f"  {pid}号狼队友: {text}" for pid, text in channel_lines)
    interim = None
    if channel_lines:
        from utils.target_parse import channel_consensus_from_lines

        interim = channel_consensus_from_lines(channel_lines, killable_ids)

    alt_ids = [i for i in killable_ids if i != interim] if interim is not None else list(killable_ids)
    alt_hint = "、".join(f"{i}号" for i in alt_ids[:4]) if alt_ids else "（见可刀列表）"

    return (
        f"【频道角色：跟麦（{speak_index + 1}/{wolf_count}）】\n"
        f"已有发言：\n{prior or '  （无）'}\n"
        "跟麦要求（须满足其一，禁止只写「同意刀X」）：\n"
        f"① 提出不同刀口（可优先考虑 {alt_hint}）并给一句理由；\n"
        "② 若仍支持队友方案，须补充与上一位不同的战术角度（如白天谁抗推、是否怕女巫/守卫）；\n"
        "③ 明确反对并写出你的刀口。"
    )
