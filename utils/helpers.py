"""
游戏状态查询的小工具函数。

被 phases、rules、roles、llm、memory 等模块复用，避免在各处重复写列表推导。
"""
import random
import re
from typing import List

from game.models import GameState, Player, Role

# 狼队频道浅层跟风（无独立战术信息）
_SHALLOW_AGREE_PATTERNS = (
    re.compile(r"^同意\s*刀\s*\d+\s*号?\s*[。.!！]?$"),
    re.compile(r"^赞同\s*刀\s*\d+\s*号?\s*[。.!！]?$"),
    re.compile(r"^支持\s*刀\s*\d+\s*号?\s*[。.!！]?$"),
    re.compile(r"^跟\s*\d+\s*号\s*一致\s*[。.!！]?$"),
    re.compile(r"^就\s*刀\s*\d+\s*号?\s*吧\s*[。.!！]?$"),
)


def get_alive_players(state: GameState) -> List[Player]:
    """按 player_id 升序返回存活玩家，保证发言/投票顺序稳定。"""
    return sorted((p for p in state.players.values() if p.is_alive), key=lambda p: p.player_id)


def get_alive_player_ids(state: GameState) -> List[int]:
    """存活玩家座位号列表（升序），供结构化 LLM 的 candidates 使用。"""
    return [p.player_id for p in get_alive_players(state)]


def get_players_by_role(state: GameState, role: Role) -> List[Player]:
    """在存活玩家中筛选指定身份（如所有狼人、预言家）。"""
    return [p for p in get_alive_players(state) if p.role == role]


def get_killable_ids(state: GameState) -> List[int]:
    """狼人可刀目标：存活且非狼人（升序）。"""
    return sorted(
        p.player_id for p in get_alive_players(state) if p.role != Role.WEREWOLF
    )


def get_seer_check_candidates(state: GameState, seer_id: int) -> List[int]:
    """预言家可查验目标：存活且非自己（升序）。"""
    return sorted(
        p.player_id for p in get_alive_players(state) if p.player_id != seer_id
    )


def get_hunter_shoot_candidates(state: GameState) -> List[int]:
    """猎人开枪目标：当前所有存活玩家（猎人已死亡）。"""
    return get_alive_player_ids(state)


def get_guard_protect_candidates(state: GameState, guard_id: int) -> List[int]:
    """
    守卫可守护目标：存活、非自己、且非上一轮已守护的玩家（升序）。
    """
    excluded = {guard_id}
    if state.guard_last_protect is not None:
        excluded.add(state.guard_last_protect)
    return sorted(
        p.player_id
        for p in get_alive_players(state)
        if p.player_id not in excluded
    )


def get_vote_candidates(state: GameState, voter_id: int) -> List[int]:
    """投票候选：存活且非投票者本人（升序）。"""
    return sorted(
        p.player_id for p in get_alive_players(state) if p.player_id != voter_id
    )


def is_valid_kill_target(state: GameState, target_id: int | None) -> bool:
    """校验座位号是否为合法狼刀目标（存活好人）。"""
    if target_id is None or target_id not in state.players:
        return False
    target = state.players[target_id]
    return target.is_alive and target.role != Role.WEREWOLF


def has_public_day_speech(state: GameState) -> bool:
    """
    是否已进入「有白天公聊」阶段。

    优先读 GameState.day_discussion_occurred（day 阶段结束时置 True），
    避免仅部分玩家 sync 过 memory 时误判为尚无公聊。
    """
    if state.day_discussion_occurred:
        return True
    if state.discussion_log:
        return True
    for mem in state.memories.values():
        if any(msg.data_type == "speech" for msg in mem.public_memory):
            return True
    return False


# 首夜/尚无公聊时，狼队频道不应引用的表述（用于轻量校验与重试）
PRE_DAY_SPEECH_FORBIDDEN_PHRASES = (
    "发言",
    "白天",
    "带节奏",
    "投票",
    "站队",
    "跟风",
)

# 已有公聊后，狼队频道不应再假装仍在首夜/首轮（无公聊阶段）
POST_DAY_WOLF_CHANNEL_FORBIDDEN_PHRASES = (
    "首夜",
    "首轮",
    "第一夜",
    "尚无白天",
    "还没有白天",
    "尚未公聊",
    "还没公聊",
)


_DISCUSSION_LINE_RE = re.compile(r"^第(\d+)轮 · 玩家(\d+)：")

# 「X号…发言/带节奏」中允许指向上轮/历史的缓冲词
_PRIOR_ROUND_IN_ATTRIBUTION = re.compile(
    r"上轮|上一轮|昨天|此前|之前|昨夜|遗言|昨晚|上局|开局前"
)

# 将某玩家的公聊行为归因到其身上（用于检测「尚未开口却被点评」）
_SPEECH_ATTRIBUTION_TO_PLAYER = re.compile(
    r"(?P<pid>\d+)\s*号"
    r"(?P<mid>[^。，；\n]{0,30}?)"
    r"(?:发言|说过|讲过|带节奏|主导节奏|投票倾向|站队|跟风|过于积极|太积极)"
)


def get_current_round_discussion_speakers(state: GameState) -> set[int]:
    """本轮白天讨论中已公开发言的座位号（不含遗言、不含当前正在生成的发言）。"""
    spoken: set[int] = set()
    for line in state.discussion_log:
        m = _DISCUSSION_LINE_RE.match(line)
        if m and int(m.group(1)) == state.round:
            spoken.add(int(m.group(2)))
    return spoken


def references_unspoken_players_discussion(
    text: str,
    speaker_id: int,
    spoken_this_round: set[int],
    valid_ids: list[int] | set[int],
) -> bool:
    """
    是否把「发言/带节奏/投票」等归因到本轮尚未开口的其他玩家。

    允许「2号上轮发言…」等明确指历史的表述。
    """
    if not text:
        return False
    valid = set(valid_ids)
    for m in _SPEECH_ATTRIBUTION_TO_PLAYER.finditer(text):
        pid = int(m.group("pid"))
        if pid == speaker_id or pid in spoken_this_round or pid not in valid:
            continue
        if _PRIOR_ROUND_IN_ATTRIBUTION.search(m.group("mid") or ""):
            continue
        return True
    return False


def format_discuss_round_hint(state: GameState, player: Player) -> str:
    """拼入白天 discuss context：本轮已发言名单与禁止编造顺序。"""
    spoken = get_current_round_discussion_speakers(state)
    if not spoken:
        return (
            "【本轮公聊】你是本轮第一位发言，此前本轮尚无任何玩家公开发言。"
            "禁止评价其他玩家的「发言」「带节奏」「投票」等——他们尚未开口。"
            "可分析平安夜、座位、神职概率，不要说「某号已经说过/太积极/主导节奏」。"
        )
    spoken_str = "、".join(f"{pid}号" for pid in sorted(spoken))
    return (
        f"【本轮公聊】本轮已发言：{spoken_str}。"
        "你只能依据上述玩家本轮发言及以往记忆推理；"
        "尚未本轮发言的玩家不要假装他们已经讲过话、带节奏或投票。"
    )


def references_unavailable_day_info(text: str) -> bool:
    """文本是否引用了尚未发生的白天公聊信息。"""
    return any(phrase in text for phrase in PRE_DAY_SPEECH_FORBIDDEN_PHRASES)


def references_stale_first_night_wording(text: str) -> bool:
    """已有白天公聊后，狼队频道是否仍使用首夜/首轮等过时表述。"""
    return any(phrase in text for phrase in POST_DAY_WOLF_CHANNEL_FORBIDDEN_PHRASES)


def order_wolves_for_channel(wolves: List[Player], round_num: int) -> List[Player]:
    """
    狼队频道发言顺序：每轮洗牌，避免固定「最小座位号」永远先开口带节奏。

    用 round + 狼座位号作种子，同轮重入稳定、不同轮顺序不同。
    """
    ordered = list(wolves)
    if len(ordered) <= 1:
        return ordered
    seed = round_num * 1009 + sum(w.player_id for w in ordered)
    rng = random.Random(seed)
    rng.shuffle(ordered)
    return ordered


def is_shallow_wolf_channel_agreement(text: str) -> bool:
    """是否为无独立理由的跟风式确认（如「同意刀9号。」）。"""
    t = (text or "").strip()
    if not t or len(t) > 28:
        return False
    return any(p.match(t) for p in _SHALLOW_AGREE_PATTERNS)
