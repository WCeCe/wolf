"""
角色处理器（RoleHandler）基类。

每个游戏身份对应一个 RoleHandler 子类，封装该身份在各阶段的固定流程：
  - run_night_camp：阵营/身份在夜晚的一整套行动（村民为空）
  - discuss：白天公聊发言
  - vote：投票放逐

引擎（game/phases）只负责阶段推进与胜负，具体「怎么聊、怎么刀」由各 Handler 实现。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from config.speech_limits import warn_if_speech_too_long
from game.constants import ROLE_KEY, role_key
from utils.helpers import (
    get_alive_player_ids,
    get_current_round_discussion_speakers,
    get_vote_candidates,
    references_unspoken_players_discussion,
)
from llm.client import generate_player_response
from llm.speech import generate_speech
from llm.vote import generate_vote
from memory.context import build_player_context

if TYPE_CHECKING:
    from game.models import GameState, Player, Role

logger = logging.getLogger("werewolf")


class RoleHandler(ABC):
    """单个身份的行为处理器：子类声明 role，并实现夜晚阵营流程（若有）。"""

    @property
    @abstractmethod
    def role(self) -> "Role":
        """本 Handler 对应的游戏身份枚举。"""
        ...

    @property
    def role_key(self) -> str:
        """LLM 配置与 prompt 使用的英文键，如 werewolf / seer。"""
        return ROLE_KEY[self.role]

    def run_night_camp(self, state: "GameState") -> None:
        """
        夜晚阵营级流程（整局该身份只执行一次，如所有狼人共用一条刀口）。

        村民等无夜晚技能的身份保持默认空实现。
        子类覆盖此方法，按固定步骤编排 LLM 调用与 night_actions 写入。
        """
        return

    def discuss(self, state: "GameState", player: "Player") -> str:
        """
        白天讨论发言的标准流程：拼 context → 调 LLM → 返回文本。

        各身份共用此实现，差异由 config/prompts 中对应 role_key 的 prompt 体现。
        """
        rk = role_key(player)
        ctx = build_player_context(state, player, "discuss")
        spoken_this_round = get_current_round_discussion_speakers(state)
        alive_ids = get_alive_player_ids(state)
        try:
            speech = generate_speech(
                player.name, rk, ctx, state.round, player_id=player.player_id
            )
            if references_unspoken_players_discussion(
                speech, player.player_id, spoken_this_round, alive_ids
            ):
                logger.warning(
                    "%s 引用了尚未本轮发言的玩家，重试一次",
                    player.name,
                )
                retry_ctx = (
                    ctx
                    + "\n【纠错】你刚才把「发言/带节奏/投票」归因到了本轮尚未开口的玩家。"
                    "请重写：只评本轮已发言者，或谈平安夜/座位/逻辑，不要编造他人已发言。"
                )
                speech = generate_speech(
                    player.name,
                    rk,
                    retry_ctx,
                    state.round,
                    player_id=player.player_id,
                )
            return warn_if_speech_too_long(
                speech, player_name=player.name, phase="discuss"
            )
        except Exception as e:
            logger.warning("%s 发言异常：%s", player.name, e)
            return f"（发言失败：{e}）"

    def last_words(self, state: "GameState", player: "Player") -> str:
        """
        被投票放逐后的遗言（GB-001）。

        写入全员 public 记忆，供后续白天/投票 context 使用。
        """
        rk = role_key(player)
        ctx = build_player_context(state, player, "last_words")
        try:
            speech = generate_player_response(
                player.name,
                rk,
                "last_words",
                ctx,
                state.round,
                player_id=player.player_id,
            )
            return warn_if_speech_too_long(
                speech, player_name=player.name, phase="last_words"
            )
        except Exception as e:
            logger.warning("%s 遗言异常：%s", player.name, e)
            return f"我是{player.player_id}号，（遗言失败：{e}）"

    def vote(self, state: "GameState", player: "Player") -> int | None:
        """
        投票放逐的标准流程：拼 context → 结构化投票 → 返回被投座位号。

        返回 None 表示 LLM 未给出合法票，由 phases/voting 随机兜底。
        """
        candidates = get_vote_candidates(state, player.player_id)
        if not candidates:
            return None

        rk = role_key(player)
        ctx = build_player_context(state, player, "vote")
        try:
            voted = generate_vote(player, rk, state, ctx)
        except Exception as e:
            logger.warning("%s 投票 LLM 失败：%s", player.name, e)
            voted = None

        if voted is not None and voted in candidates:
            return voted
        return None
