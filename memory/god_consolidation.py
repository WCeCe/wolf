"""
5.7 神职私密记忆账本化：用 GameState 结构化字段替代 private_memory 叙述送入 LLM。

publish_private 仍写入记忆仓（调试/存档）；出库时由 selection 跳过私密原文，由本模块生成短账本。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.models import Role

if TYPE_CHECKING:
    from game.models import GameState


def format_seer_check_history_body(state: "GameState") -> str:
    """预言家查验史紧凑串（供白天账本与夜晚 context 共用）。"""
    if not state.seer_check_history:
        return ""
    return "；".join(
        f"{pid}号→{role}" for pid, role in state.seer_check_history
    )


def format_seer_private_ledger(state: "GameState") -> str:
    body = format_seer_check_history_body(state)
    if not body:
        return ""
    return f"【预言家私密账本】以往查验：{body}"


def format_witch_private_ledger(state: "GameState") -> str:
    antidote = "可用" if state.witch_has_antidote else "已用完"
    poison = "可用" if state.witch_has_poison else "已用完"
    lines = [
        "【女巫私密账本】",
        f"解药：{antidote}；毒药：{poison}",
    ]
    lines.extend(state.witch_potion_log)
    return "\n".join(lines)


def format_guard_private_ledger(state: "GameState") -> str:
    if state.guard_last_protect is not None:
        pid = state.guard_last_protect
        if pid in state.players:
            p = state.players[pid]
            return (
                f"【守卫私密账本】上一轮守护：{pid}号({p.name})"
                "（今夜不可再守此人）"
            )
        return f"【守卫私密账本】上一轮守护：{pid}号（今夜不可再守此人）"
    return "【守卫私密账本】上一轮未守护任何人（或为首夜）。"


def format_god_private_ledger(state: "GameState", role: Role) -> str:
    if role == Role.SEER:
        return format_seer_private_ledger(state)
    if role == Role.WITCH:
        return format_witch_private_ledger(state)
    if role == Role.GUARD:
        return format_guard_private_ledger(state)
    return ""


def append_witch_potion_log(
    state: "GameState",
    *,
    round_num: int,
    used_antidote: bool,
    wolf_kill_id: int | None,
    poison_target: int | None,
    had_antidote_choice: bool,
    had_poison_choice: bool,
) -> None:
    """女巫当夜行动后写入一行紧凑账本（供白天出库）。"""
    if had_antidote_choice:
        if used_antidote and wolf_kill_id is not None:
            state.witch_potion_log.append(
                f"第{round_num}轮：解药救{wolf_kill_id}号（狼刀）"
            )
        else:
            state.witch_potion_log.append(f"第{round_num}轮：未用解药")
    if had_poison_choice:
        if poison_target is not None:
            state.witch_potion_log.append(
                f"第{round_num}轮：毒药{poison_target}号"
            )
        else:
            state.witch_potion_log.append(f"第{round_num}轮：未用毒药")
