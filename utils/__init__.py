"""
通用工具：日志、局面查询、文本解析等。

业务包（game / roles / llm / memory）应从此包导入工具函数，而非在 game 下重复放置。
"""
from .helpers import (
    PRE_DAY_SPEECH_FORBIDDEN_PHRASES,
    get_alive_player_ids,
    get_alive_players,
    get_guard_protect_candidates,
    get_hunter_shoot_candidates,
    get_killable_ids,
    get_players_by_role,
    get_seer_check_candidates,
    get_vote_candidates,
    has_public_day_speech,
    is_valid_kill_target,
    references_unavailable_day_info,
)
from .logging import setup_logger
from .target_parse import (
    channel_consensus_from_lines,
    channel_primary_targets,
    consensus_target,
    is_strong_channel_consensus,
    parse_target_ids,
)

__all__ = [
    "PRE_DAY_SPEECH_FORBIDDEN_PHRASES",
    "setup_logger",
    "get_alive_players",
    "get_alive_player_ids",
    "get_players_by_role",
    "get_killable_ids",
    "get_seer_check_candidates",
    "get_hunter_shoot_candidates",
    "get_guard_protect_candidates",
    "get_vote_candidates",
    "is_valid_kill_target",
    "has_public_day_speech",
    "references_unavailable_day_info",
    "parse_target_ids",
    "consensus_target",
    "channel_primary_targets",
    "channel_consensus_from_lines",
    "is_strong_channel_consensus",
]
