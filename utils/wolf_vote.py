"""
狼队夜晚刀口投票：严格多数当选 + 平票决胜链（首麦票 → 讨论提及 → 随机）。
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from utils.target_parse import parse_target_ids

ChannelLine = Tuple[int, str]


@dataclass
class WolfKillVoteResult:
    """狼队表决结果。"""

    target_id: int
    votes: Dict[int, Optional[int]]  # 狼座位号 → 刀口或 None（弃权/无效）
    tally: Dict[int, int]  # 刀口 → 得票
    resolution: str  # 决议方式，供日志与账本
    detail: str  # 人类可读说明


def votes_needed(wolf_count: int) -> int:
    """当选所需最少票数（严格多数；2 狼须全票一致）。"""
    if wolf_count <= 1:
        return 1
    if wolf_count == 2:
        return 2
    return wolf_count // 2 + 1


def format_vote_ballot(votes: Dict[int, Optional[int]]) -> str:
    parts: List[str] = []
    for wid in sorted(votes):
        t = votes[wid]
        if t is None:
            parts.append(f"{wid}号→弃权")
        else:
            parts.append(f"{wid}号→{t}号")
    return ", ".join(parts)


def _mention_counts_for_targets(
    channel_lines: List[ChannelLine],
    killable_ids: List[int],
    candidates: List[int],
) -> Counter:
    counts: Counter = Counter()
    candidate_set = set(candidates)
    for _, text in channel_lines:
        for tid in parse_target_ids(text, killable_ids):
            if tid in candidate_set:
                counts[tid] += 1
    return counts


def _tie_break(
    tied_targets: List[int],
    *,
    first_speaker_id: int,
    votes: Dict[int, Optional[int]],
    channel_lines: List[ChannelLine],
    killable_ids: List[int],
) -> Tuple[int, str]:
    """T1 首麦票 → T3 讨论提及 → T5 随机。"""
    if not tied_targets:
        raise ValueError("tie_break requires non-empty tied_targets")

    fs_vote = votes.get(first_speaker_id)
    if fs_vote is not None and fs_vote in tied_targets:
        return fs_vote, "tie_first_speaker"

    mentions = _mention_counts_for_targets(channel_lines, killable_ids, tied_targets)
    if mentions:
        top_count = mentions.most_common(1)[0][1]
        leaders = [t for t, c in mentions.items() if c == top_count]
        if len(leaders) == 1:
            return leaders[0], "tie_discussion_mentions"

    chosen = random.choice(tied_targets)
    return chosen, "tie_random"


def resolve_wolf_kill_vote(
    votes: Dict[int, Optional[int]],
    killable_ids: List[int],
    channel_lines: List[ChannelLine],
    first_speaker_id: int,
    wolf_count: int,
) -> WolfKillVoteResult:
    """
    根据各狼投票决议刀口。

    votes: 每位狼人的 target_id；None 表示弃权或无效票。
    """
    threshold = votes_needed(wolf_count)
    valid = {wid: t for wid, t in votes.items() if t is not None and t in killable_ids}
    tally = Counter(valid.values())

    if not tally:
        target = random.choice(killable_ids)
        return WolfKillVoteResult(
            target_id=target,
            votes=votes,
            tally=dict(tally),
            resolution="no_valid_votes_random",
            detail=f"无有效票，随机刀{target}号",
        )

    # 严格多数：唯一目标得票 >= threshold
    majority_winners = [t for t, c in tally.items() if c >= threshold]
    if len(majority_winners) == 1:
        target = majority_winners[0]
        return WolfKillVoteResult(
            target_id=target,
            votes=votes,
            tally=dict(tally),
            resolution="strict_majority",
            detail=f"{target}号得票{tally[target]}/{wolf_count}（须≥{threshold}）",
        )
    if len(majority_winners) > 1:
        target, how = _tie_break(
            majority_winners,
            first_speaker_id=first_speaker_id,
            votes=votes,
            channel_lines=channel_lines,
            killable_ids=killable_ids,
        )
        return WolfKillVoteResult(
            target_id=target,
            votes=votes,
            tally=dict(tally),
            resolution=how,
            detail=f"严格多数并列，决胜→{target}号",
        )

    max_votes = max(tally.values())
    top_targets = sorted(t for t, c in tally.items() if c == max_votes)

    if len(top_targets) == 1:
        tied = top_targets
    else:
        tied = top_targets

    target, how = _tie_break(
        tied,
        first_speaker_id=first_speaker_id,
        votes=votes,
        channel_lines=channel_lines,
        killable_ids=killable_ids,
    )
    return WolfKillVoteResult(
        target_id=target,
        votes=votes,
        tally=dict(tally),
        resolution=how,
        detail=f"未达{threshold}票，最高{tied}，决胜→{target}号",
    )


def format_vote_result_message(
    result: WolfKillVoteResult, *, round_num: int
) -> str:
    """狼队频道公布的表决结果（一行）。"""
    ballot = format_vote_ballot(result.votes)
    tally_str = "，".join(f"{t}号({c}票)" for t, c in sorted(result.tally.items()))
    return (
        f"第{round_num}轮狼队投票：{ballot}。"
        f"计票：{tally_str or '无'}。"
        f"决议：刀{result.target_id}号（{result.detail}）。"
    )
