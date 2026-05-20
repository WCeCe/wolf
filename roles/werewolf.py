"""
狼人角色处理器（WerewolfHandler）。

夜晚标准流程（run_night_camp）：
  1. 狼队频道讨论 — 每名存活狼人依次发言
  2. 狼队刀口投票 — 每人结构化投 1 票，严格多数当选
  3. 平票按：首麦票 → 讨论提及次数 → 随机
  4. 写入 night_actions.wolf_kill，并 publish 表决结果与刀口
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from game.ledger import record_wolf_kill_vote
from game.models import Role
from llm.wolf_summary import summarize_wolf_channel
from llm.wolf_vote import collect_wolf_kill_votes
from llm.speech import generate_werewolf_channel_speech
from memory.context import build_wolf_kill_vote_context, build_werewolf_channel_context
from memory.publish import publish_werewolf
from memory.wolf_summary_store import apply_wolf_night_summary
from utils.helpers import (
    get_killable_ids,
    get_players_by_role,
    has_public_day_speech,
    is_shallow_wolf_channel_agreement,
    is_valid_kill_target,
    order_wolves_for_channel,
    references_stale_first_night_wording,
    references_unavailable_day_info,
)
from utils.wolf_channel import build_channel_speak_hint
from utils.wolf_vote import (
    format_vote_result_message,
    resolve_wolf_kill_vote,
)

from .base import RoleHandler

if TYPE_CHECKING:
    from game.models import GameState, Player

logger = logging.getLogger("werewolf")

# (狼人座位号, 频道发言文本)
ChannelLine = tuple[int, str]


class WerewolfHandler(RoleHandler):
    """狼人阵营处理器：讨论 → 表决 → 落刀。"""

    @property
    def role(self) -> Role:
        return Role.WEREWOLF

    def run_night_camp(self, state: "GameState") -> None:
        wolves = get_players_by_role(state, Role.WEREWOLF)
        if not wolves:
            return

        killable_ids = get_killable_ids(state)
        if not killable_ids:
            return

        speak_order = order_wolves_for_channel(wolves, state.round)
        channel_lines = self._run_wolf_channel(state, speak_order, killable_ids)

        publish_werewolf(
            state,
            f"第{state.round}轮：讨论结束，开始刀口投票（须≥{max(1, len(wolves) // 2 + 1) if len(wolves) > 2 else len(wolves)}票当选）。",
            sender="system",
            data_type="system_info",
        )
        logger.info("--- 狼队刀口投票 ---")

        raw_votes = collect_wolf_kill_votes(
            state,
            wolves,
            speak_order,
            channel_lines,
            killable_ids,
            build_wolf_kill_vote_context,
        )

        first_speaker_id = speak_order[0].player_id
        vote_result = resolve_wolf_kill_vote(
            raw_votes,
            killable_ids,
            channel_lines,
            first_speaker_id,
            len(wolves),
        )

        result_msg = format_vote_result_message(vote_result, round_num=state.round)
        publish_werewolf(state, result_msg, sender="system", data_type="system_info")
        record_wolf_kill_vote(
            state,
            f"狼队投票刀{vote_result.target_id}号（{vote_result.detail}）",
        )
        logger.info(
            "[狼队投票] %s | 决议刀 %s 号（%s）",
            result_msg,
            vote_result.target_id,
            vote_result.resolution,
        )

        target_id = vote_result.target_id
        leader = speak_order[0]

        if is_valid_kill_target(state, target_id):
            self._apply_wolf_kill(
                state, leader, target_id, channel_lines, vote_summary=result_msg
            )
        else:
            fallback = random.choice(killable_ids)
            logger.info("狼队表决刀口无效，随机击杀：%s 号", fallback)
            self._apply_wolf_kill(
                state, leader, fallback, channel_lines, vote_summary=result_msg
            )

    def _run_wolf_channel(
        self,
        state: "GameState",
        speak_order: list["Player"],
        killable_ids: list[int],
    ) -> list[ChannelLine]:
        """狼队频道讨论，返回当夜发言列表。"""
        logger.info("--- 狼队频道讨论 ---")
        channel_lines: list[ChannelLine] = []
        wolf_count = len(speak_order)
        if wolf_count > 1:
            order_ids = "→".join(str(w.player_id) for w in speak_order)
            logger.info("狼队频道发言顺序（本轮）：%s", order_ids)

        for speak_index, wolf in enumerate(speak_order):
            try:
                ctx = build_werewolf_channel_context(state, wolf)
                ctx += "\n" + build_channel_speak_hint(
                    speak_index=speak_index,
                    wolf_count=wolf_count,
                    channel_lines=channel_lines,
                    killable_ids=killable_ids,
                )

                speech = generate_werewolf_channel_speech(wolf, state, ctx)
                if not has_public_day_speech(state) and references_unavailable_day_info(
                    speech
                ):
                    logger.warning(
                        "%s 狼队频道引用了尚未发生的白天信息，重试一次",
                        wolf.name,
                    )
                    retry_ctx = (
                        ctx
                        + "\n【纠错】你刚才的表述引用了不存在的白天公聊，请重写："
                        "只写刀几号，理由用座位/战术/神职猜测，不要提发言、白天、带节奏、投票。"
                    )
                    speech = generate_werewolf_channel_speech(wolf, state, retry_ctx)
                elif has_public_day_speech(state) and references_stale_first_night_wording(
                    speech
                ):
                    logger.warning(
                        "%s 狼队频道使用了首夜/首轮等过时表述（当前已有公聊），重试一次",
                        wolf.name,
                    )
                    retry_ctx = (
                        ctx
                        + "\n【纠错】本局已进行过白天公聊，请勿使用「首夜」「首轮」等词。"
                        f"请按当前第{state.round}轮局面重写刀口（一句、带座位号）。"
                    )
                    speech = generate_werewolf_channel_speech(wolf, state, retry_ctx)

                if speak_index > 0 and is_shallow_wolf_channel_agreement(speech):
                    logger.warning(
                        "%s 狼队频道跟风式回复，要求补充独立刀口或理由后重试",
                        wolf.name,
                    )
                    retry_ctx = (
                        ctx
                        + "\n【纠错】你刚才只有「同意刀X」式附和，没有独立判断。"
                        "请重写：要么提出另一刀口+理由，要么支持队友方案但补充不同战术角度（一句、带座位号）。"
                    )
                    speech = generate_werewolf_channel_speech(wolf, state, retry_ctx)

                channel_lines.append((wolf.player_id, speech))
                publish_werewolf(
                    state,
                    speech,
                    sender=str(wolf.player_id),
                    data_type="speech",
                )
            except Exception as e:
                logger.warning("%s 狼队频道发言失败：%s", wolf.name, e)

        return channel_lines

    def _apply_wolf_kill(
        self,
        state: "GameState",
        leader: "Player",
        target_id: int,
        channel_lines: list[ChannelLine],
        *,
        vote_summary: str | None = None,
    ) -> None:
        """写入 wolf_kill、通知狼队频道，并生成 LLM 战术摘要供白天使用。"""
        state.night_actions["wolf_kill"] = target_id
        logger.info("狼人击杀目标：%s 号", target_id)
        publish_werewolf(
            state,
            f"本轮刀口：{target_id} 号",
            sender=str(leader.player_id),
            data_type="action",
        )
        summary = summarize_wolf_channel(
            state,
            channel_lines,
            target_id,
            vote_summary=vote_summary,
        )
        apply_wolf_night_summary(state, summary)
        logger.info("狼队战术摘要：%s", summary)
