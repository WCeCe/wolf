"""
从发言文本中解析座位号，用于狼队协商刀口、投票等。
"""
import re
from collections import Counter
from typing import Iterable


def parse_target_ids(text: str, valid_ids: Iterable[int]) -> list[int]:
    """从中文对局发言中提取合法座位号（去重保序）。"""
    if not text or not valid_ids:
        return []
    valid = set(valid_ids)
    found: list[int] = []

    def add(n: int) -> None:
        if n in valid and n not in found:
            found.append(n)

    for m in re.finditer(r"(\d+)\s*号", text):
        add(int(m.group(1)))
    for m in re.finditer(r"(?:刀|杀|出|投|查验|查|救|毒)\s*(\d+)", text):
        add(int(m.group(1)))
    for m in re.finditer(r"\b(\d+)\b", text):
        add(int(m.group(1)))
    return found


def consensus_target(mentions: list[int]) -> int | None:
    """取出现次数最多的座位号；至少出现一次即返回。"""
    if not mentions:
        return None
    target, _ = Counter(mentions).most_common(1)[0]
    return target


def channel_primary_targets(
    channel_lines: list[tuple[int, str]], valid_ids: list[int]
) -> list[int]:
    """从当夜狼队频道发言中提取每位狼人的主刀口（首个合法座位号）。"""
    primaries: list[int] = []
    for _, content in channel_lines:
        ids = parse_target_ids(content, valid_ids)
        if ids:
            primaries.append(ids[0])
    return primaries


def channel_consensus_from_lines(
    channel_lines: list[tuple[int, str]], valid_ids: list[int]
) -> int | None:
    """仅基于当夜频道发言统计协商刀口（不含历史轮次）。"""
    mentions: list[int] = []
    for _, content in channel_lines:
        mentions.extend(parse_target_ids(content, valid_ids))
    return consensus_target(mentions)


def is_strong_channel_consensus(
    primaries: list[int], agreed: int | None, wolf_count: int
) -> bool:
    """
    频道刀口是否足够一致，可直接落刀而无需再调 LLM。

    - 全员主刀口相同且等于 agreed
    - 或 agreed 获得严格多数（超过半数狼人主刀口一致）
    """
    if agreed is None or not primaries:
        return False
    if len(set(primaries)) == 1 and primaries[0] == agreed:
        return True
    need = wolf_count // 2 + 1
    return Counter(primaries).get(agreed, 0) >= need
