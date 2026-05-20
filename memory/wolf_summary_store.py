"""将狼队夜间摘要写入各狼人 PlayerMemory。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.models import Role

if TYPE_CHECKING:
    from game.models import GameState


def apply_wolf_night_summary(state: "GameState", summary: str) -> None:
    """每夜落刀后调用，所有存活狼人共用同一条摘要文案。"""
    if not state.memories:
        return
    for pid, player in state.players.items():
        if player.role != Role.WEREWOLF:
            continue
        mem = state.memories.get(pid)
        if mem is not None:
            mem.wolf_night_summary = summary
