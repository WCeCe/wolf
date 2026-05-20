"""context 拼接小工具（不改变记忆出库策略）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from game.models import GameState, Player


def append_player_memory_block(
    state: "GameState",
    player: "Player",
    phase: str,
    lines: List[str],
) -> None:
    """若该玩家有记忆出库内容，追加到 lines 末尾。"""
    if not state.memories or player.player_id not in state.memories:
        return
    memory_text = state.memories[player.player_id].get_context_for_llm(
        phase,
        current_round=state.round,
        role=player.role,
        round_ledger=state.round_ledger,
    )
    if memory_text:
        lines.append(memory_text)
