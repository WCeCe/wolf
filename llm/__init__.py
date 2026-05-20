"""大模型调用层：自由文本、发言、夜晚结构化行动。"""
from .client import generate_player_response
from .night import generate_night_action
from .speech import generate_speech, generate_werewolf_channel_speech
from .structured import call_structured_completion, client_from_cfg
from .hunter import generate_hunter_shoot
from .vote import generate_vote
from .witch import generate_witch_night_action
from .wolf_vote import generate_wolf_kill_vote

__all__ = [
    "generate_player_response",
    "generate_speech",
    "generate_werewolf_channel_speech",
    "generate_night_action",
    "generate_vote",
    "generate_witch_night_action",
    "generate_wolf_kill_vote",
    "generate_hunter_shoot",
    "call_structured_completion",
    "client_from_cfg",
]
