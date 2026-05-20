"""
5.1 阶段感知记忆筛选；5.2 远轮场面由局面账本补充。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from game.ledger import RoundLedger, format_ledger_block
from game.models import Role

from .message import Message
from .public_split import split_public_messages
from .policy_config import (
    SPEECH_ROUNDS_DISCUSS,
    SPEECH_ROUNDS_HUNTER_SHOOT,
    SPEECH_ROUNDS_LAST_WORDS,
    SPEECH_ROUNDS_VOTE,
    WOLF_SYSTEM_LAST_N,
)

_ROUND_RE = re.compile(r"第(\d+)轮")

_GOD_ROLES = frozenset({Role.SEER, Role.WITCH, Role.GUARD})


@dataclass
class SelectedMemory:
    """筛选后的消息子集，供 formatter 使用。"""

    public_system: List[Message]
    public_speech: List[Message]
    private_messages: List[Message]
    werewolf_messages: List[Message]
    wolf_summary: Optional[str] = None
    speech_rounds_k: int = 0
    ledger_block: str = ""


def _empty_selected() -> SelectedMemory:
    """非神职在 phase=night 等场景下无记忆出库。"""
    return SelectedMemory([], [], [], [], None, 0, "")


def message_round(msg: Message) -> Optional[int]:
    if msg.round is not None:
        return msg.round
    m = _ROUND_RE.search(str(msg.content))
    return int(m.group(1)) if m else None


def _filter_speech_recent(
    speech: List[Message], current_round: int, k: int
) -> List[Message]:
    if k <= 0:
        return []
    min_round = current_round - k + 1
    kept: List[Message] = []
    for msg in speech:
        r = message_round(msg)
        if r is None:
            continue
        if r >= min_round:
            kept.append(msg)
    return kept


def _filter_werewolf_tonight(
    werewolf_memory: List[Message], current_round: int
) -> List[Message]:
    kept: List[Message] = []
    for msg in werewolf_memory:
        r = message_round(msg)
        if r is None or r == current_round:
            kept.append(msg)
    return kept


def _speech_rounds_for_phase(phase: str) -> int:
    if phase == "vote":
        return SPEECH_ROUNDS_VOTE
    if phase == "hunter_shoot":
        return SPEECH_ROUNDS_HUNTER_SHOOT
    if phase == "discuss":
        return SPEECH_ROUNDS_DISCUSS
    if phase == "last_words":
        return SPEECH_ROUNDS_LAST_WORDS
    return 0


def _select_werewolf_night(
    *,
    role: Role,
    phase: str,
    current_round: int,
    system_all: List[Message],
    werewolf_memory: List[Message],
    wolf_night_summary: Optional[str],
    round_ledger: RoundLedger | None,
) -> SelectedMemory:
    """werewolf_channel / night_wolf_kill 共用出库（仅参数 wolf_summary、ledger 不同）。"""
    if role != Role.WEREWOLF:
        return _empty_selected()
    ledger_block = ""
    if phase == "werewolf_channel":
        ledger_block = format_ledger_block(
            round_ledger,
            current_round=current_round,
            speech_rounds_k=0,
            include_all=True,
        )
    return SelectedMemory(
        public_system=system_all[-WOLF_SYSTEM_LAST_N:],
        public_speech=[],
        private_messages=[],
        werewolf_messages=_filter_werewolf_tonight(werewolf_memory, current_round),
        wolf_summary=wolf_night_summary if phase == "night_wolf_kill" else None,
        speech_rounds_k=0,
        ledger_block=ledger_block,
    )


def _filter_system_recent_rounds(
    system: List[Message], min_speech_round: int
) -> List[Message]:
    """远轮 system_info 已由账本覆盖，避免与【局面账本】重复。"""
    if min_speech_round <= 1:
        return list(system)
    kept: List[Message] = []
    for msg in system:
        r = message_round(msg)
        if r is None or r >= min_speech_round:
            kept.append(msg)
    return kept


def _finalize_with_ledger(
    *,
    ledger: RoundLedger | None,
    current_round: int,
    speech_rounds_k: int,
    system_all: List[Message],
    public_speech: List[Message],
    private_messages: List[Message],
    werewolf_messages: List[Message],
    wolf_summary: Optional[str],
    include_all_ledger: bool = False,
) -> SelectedMemory:
    min_speech = (
        current_round - speech_rounds_k + 1 if speech_rounds_k > 0 else 1
    )
    ledger_block = format_ledger_block(
        ledger,
        current_round=current_round,
        speech_rounds_k=speech_rounds_k,
        include_all=include_all_ledger,
    )
    if speech_rounds_k > 0 and not include_all_ledger:
        system_kept = _filter_system_recent_rounds(system_all, min_speech)
    else:
        system_kept = list(system_all)

    return SelectedMemory(
        public_system=system_kept,
        public_speech=public_speech,
        private_messages=private_messages,
        werewolf_messages=werewolf_messages,
        wolf_summary=wolf_summary,
        speech_rounds_k=speech_rounds_k,
        ledger_block=ledger_block,
    )


def select_messages(
    *,
    role: Role,
    phase: str,
    current_round: int,
    public_memory: List[Message],
    private_memory: List[Message],
    werewolf_memory: List[Message],
    wolf_night_summary: Optional[str],
    round_ledger: RoundLedger | None = None,
) -> SelectedMemory:
    """按 5.1 / 5.2 规则筛选三层记忆。"""
    system_all, speech_all = split_public_messages(public_memory)

    if phase in ("werewolf_channel", "night_wolf_kill", "wolf_kill_vote"):
        return _select_werewolf_night(
            role=role,
            phase=phase,
            current_round=current_round,
            system_all=system_all,
            werewolf_memory=werewolf_memory,
            wolf_night_summary=wolf_night_summary,
            round_ledger=round_ledger,
        )

    if phase == "night":
        if role not in _GOD_ROLES:
            return _empty_selected()
        return _finalize_with_ledger(
            ledger=round_ledger,
            current_round=current_round,
            speech_rounds_k=0,
            system_all=system_all,
            public_speech=[],
            private_messages=[],
            werewolf_messages=[],
            wolf_summary=None,
            include_all_ledger=True,
        )

    k = _speech_rounds_for_phase(phase)
    speech_kept = _filter_speech_recent(speech_all, current_round, k)

    # 5.7：神职私密由 GameState 账本注入 build_player_context，不再出库 private 原文。
    # 村民/狼人白天 discuss/vote 仍不注入 private（与 5.1 一致）；猎人走 hunter_shoot 专用阶段。
    private_kept: List[Message] = []

    wolf_summary_out: Optional[str] = None
    if role == Role.WEREWOLF and phase in ("discuss", "vote"):
        wolf_summary_out = wolf_night_summary

    return _finalize_with_ledger(
        ledger=round_ledger,
        current_round=current_round,
        speech_rounds_k=k,
        system_all=system_all,
        public_speech=speech_kept,
        private_messages=private_kept,
        werewolf_messages=[],
        wolf_summary=wolf_summary_out,
    )
