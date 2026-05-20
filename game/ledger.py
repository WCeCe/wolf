"""
5.2 结构化局面账本：由引擎在阶段结束时写入，零 LLM。

供 memory 层在远轮公聊被 5.1 裁掉时，仍保留死讯/投票/开枪等要点。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from game.models import GameState


@dataclass
class RoundLedger:
    """按轮次累积局面要点；同一轮多条 segment 在展示时合并为一行。"""

    segments: Dict[int, List[str]] = field(default_factory=dict)

    def add(self, round_num: int, segment: str) -> None:
        if not segment:
            return
        self.segments.setdefault(round_num, []).append(segment)

    def lines_up_to(self, max_round: int) -> List[str]:
        """返回 [R1] … 形式，仅包含 round <= max_round 的条目。"""
        if max_round < 1:
            return []
        out: List[str] = []
        for r in sorted(n for n in self.segments if n <= max_round):
            body = "；".join(self.segments[r])
            out.append(f"[R{r}] {body}")
        return out


def _ledger(state: "GameState") -> RoundLedger:
    if state.round_ledger is None:
        state.round_ledger = RoundLedger()
    return state.round_ledger


def record_game_start(state: "GameState") -> None:
    n = len(state.players)
    _ledger(state).add(state.round, f"开局{n}人标准局")


def record_night_deaths(state: "GameState", deaths: List[int]) -> None:
    r = state.round
    if not deaths:
        _ledger(state).add(r, "昨夜平安夜")
        return
    if len(deaths) == 1:
        _ledger(state).add(r, f"昨夜{deaths[0]}号死亡")
    else:
        ids = "、".join(str(d) for d in sorted(deaths))
        _ledger(state).add(r, f"昨夜{ids}号死亡")


def record_hunter_shoot(state: "GameState", hunter_id: int, target_id: int) -> None:
    _ledger(state).add(
        state.round,
        f"猎人{hunter_id}号开枪带走{target_id}号",
    )


def record_hunter_cannot_shoot(state: "GameState", hunter_id: int, reason: str) -> None:
    if reason == "poisoned":
        _ledger(state).add(state.round, f"猎人{hunter_id}号被毒死未开枪")
    elif reason == "already_used":
        _ledger(state).add(state.round, f"猎人{hunter_id}号出局未再开枪")


def record_vote(
    state: "GameState",
    *,
    eliminated: int | None = None,
    votes: int | None = None,
    tied_ids: List[int] | None = None,
    no_votes: bool = False,
) -> None:
    r = state.round
    if no_votes:
        _ledger(state).add(r, "投票无人得票")
        return
    if tied_ids:
        ids = "、".join(str(i) for i in sorted(tied_ids))
        _ledger(state).add(r, f"投票{ids}号平票无人出局")
        return
    if eliminated is not None:
        tail = f"得票{votes}" if votes is not None else ""
        seg = f"投票{eliminated}号被放逐"
        if tail:
            seg += f"（{tail}）"
        _ledger(state).add(r, seg)


def record_wolf_kill_vote(state: "GameState", summary: str) -> None:
    """狼队夜晚刀口表决要点（零 LLM）。"""
    if summary:
        _ledger(state).add(state.round, summary)


def record_last_words(state: "GameState", player_id: int, text: str) -> None:
    """放逐遗言写入账本（截断过长文本，供远轮 memory 保留要点）。"""
    snippet = (text or "").strip().replace("\n", " ")
    if len(snippet) > 80:
        snippet = snippet[:80] + "…"
    if snippet:
        _ledger(state).add(state.round, f"{player_id}号遗言：{snippet}")


def ledger_max_round_for_context(current_round: int, speech_rounds_k: int) -> int:
    """
    与 5.1 配合：公聊保留最近 K 轮时，账本覆盖更早轮次。

    K=0 时不展示账本；K>=1 时展示 round <= current_round - K 的条目。
    """
    if speech_rounds_k <= 0:
        return 0
    return current_round - speech_rounds_k


def format_ledger_block(
    ledger: RoundLedger | None,
    *,
    current_round: int,
    speech_rounds_k: int,
    include_all: bool = False,
) -> str:
    """格式化为 【局面账本】 文本块；无内容返回空字符串。"""
    if ledger is None or not ledger.segments:
        return ""
    max_r = current_round if include_all else ledger_max_round_for_context(
        current_round, speech_rounds_k
    )
    lines = ledger.lines_up_to(max_r)
    if not lines:
        return ""
    body = "\n".join(lines)
    return f"【局面账本（第1～{max_r}轮要点）】\n{body}"
