"""
阶段二：白天讨论（Phase.DAY_DISCUSSION）。

顺序：
  1. 结算昨夜死亡（狼刀 + 女巫救/毒）
  2. 公布昨夜死讯（先于猎人，便于猎人/他人记忆同步）
  3. 昨夜死亡的猎人尝试开枪 → 公布开枪结果
  4. 胜负判定
  5. 每名存活玩家依次发言 — 委托对应 RoleHandler.discuss
"""
import logging

from utils.helpers import get_alive_players
from game.ledger import record_night_deaths
from game.models import GameState, Phase
from game.night_resolution import resolve_night_deaths, wolf_kill_blocked_by
from game.rules import check_game_over
from memory.publish import publish_global
from roles.registry import (
    announce_hunter_shoots,
    get_player_handler,
    resolve_hunter_shoots_for_deaths,
)

logger = logging.getLogger("werewolf")


_PEACEFUL_NIGHT_PUBLIC = (
    "昨夜平安夜（无人死亡）。"
    "狼人是否出刀、刀口指向谁，除女巫使用解药时女巫可知外，"
    "其余玩家（含被狼人选择的目标）均不可知，请勿在公聊中断言「某号被刀」。"
)


def _announce_night_deaths(state: GameState, deaths: list[int]) -> None:
    """根据死亡列表生成公开死讯（不透露守卫挡刀、女巫是否救人）。"""
    if not deaths:
        announce = f"第{state.round}轮：{_PEACEFUL_NIGHT_PUBLIC}"
        state.public_log.append(announce)
        publish_global(state, announce)
        logger.info("昨夜平安夜。")
        return

    if len(deaths) == 1:
        announce = f"第{state.round}轮：昨夜 {deaths[0]} 号玩家死亡。"
    else:
        ids = "、".join(f"{d} 号" for d in deaths)
        announce = f"第{state.round}轮：昨夜 {ids} 玩家死亡。"

    state.public_log.append(announce)
    publish_global(state, announce)
    for d in deaths:
        logger.info("昨夜 %s 号死亡。", d)


def day_discussion_phase(state: GameState) -> None:
    logger.info("=== 白天讨论 ===")
    state.phase = Phase.DAY_DISCUSSION

    deaths = resolve_night_deaths(state)
    blocked = wolf_kill_blocked_by(state)
    if blocked == "guard":
        wolf_kill_id = state.night_actions.get("wolf_kill")
        logger.info(
            "狼刀目标 %s 号被守卫抵挡，无人死亡（公开仍为平安夜）",
            wolf_kill_id,
        )
    elif blocked == "witch_save":
        wolf_kill_id = state.night_actions.get("wolf_kill")
        logger.info(
            "狼刀目标 %s 号被女巫救活，无人死亡（公开仍为平安夜）",
            wolf_kill_id,
        )
    record_night_deaths(state, deaths)
    _announce_night_deaths(state, deaths)
    hunter_shoots = resolve_hunter_shoots_for_deaths(state, deaths, "night")
    if hunter_shoots:
        header = f"第{state.round}轮：公布猎人技能结果（与昨夜死讯分开）。"
        state.public_log.append(header)
        publish_global(state, header, data_type="system_info")
        announce_hunter_shoots(state, hunter_shoots)

    if check_game_over(state):
        return

    for player in get_alive_players(state):
        handler = get_player_handler(player)
        speech = handler.discuss(state, player)

        line = f"第{state.round}轮 · {player.name}：{speech}"
        state.discussion_log.append(line)
        publish_global(state, speech, sender=str(player.player_id), data_type="speech")
        logger.info("%s（%s）：%s", player.name, player.role.value, speech)

    state.day_discussion_occurred = True
    state.phase = Phase.VOTING
