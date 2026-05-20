"""
阶段三：投票放逐（Phase.VOTING）。

每名存活玩家委托 RoleHandler.vote 结构化投票；失败时随机兜底。
计票规则：得票最高且唯一者被放逐；平票则本轮无人出局。
结束后 round+1，phase 回到 NIGHT。
"""
import logging
import random
from collections import Counter

from utils.helpers import get_alive_players, get_vote_candidates
from game.ledger import record_last_words, record_vote
from game.models import GameState, Phase
from game.rules import check_game_over
from memory.publish import eliminate_player, publish_global
from roles.registry import (
    announce_hunter_shoots,
    get_player_handler,
    resolve_hunter_shoots_for_deaths,
)

logger = logging.getLogger("werewolf")


def _elimination_last_words(state: GameState, eliminated: int) -> None:
    """被放逐玩家发表遗言并写入全员记忆（在猎人开枪之前）。"""
    player = state.players[eliminated]
    handler = get_player_handler(player)

    announce = f"第{state.round}轮：{eliminated}号玩家发表遗言。"
    state.public_log.append(announce)
    publish_global(state, announce, data_type="system_info")
    logger.info("%s 号玩家发表遗言。", eliminated)

    speech = handler.last_words(state, player)
    line = f"第{state.round}轮 · {player.name}遗言：{speech}"
    state.discussion_log.append(line)
    publish_global(state, speech, sender=str(eliminated), data_type="speech")
    record_last_words(state, eliminated, speech)
    logger.info("%s（%s）遗言：%s", player.name, player.role.value, speech)


def voting_phase(state: GameState) -> None:
    logger.info("=== 投票放逐 ===")
    state.phase = Phase.VOTING
    state.vote_results = {}

    alive = get_alive_players(state)

    for voter in alive:
        candidates = get_vote_candidates(state, voter.player_id)
        if not candidates:
            continue

        handler = get_player_handler(voter)
        voted = handler.vote(state, voter)

        if voted is None or voted not in candidates:
            voted = random.choice(candidates)
            logger.warning("%s 投票无效，随机投给 %s 号", voter.name, voted)

        state.vote_results[voter.player_id] = voted
        logger.info("%s（%s）投票给 %s 号", voter.name, voter.role.value, voted)

    tally = Counter(state.vote_results.values())

    if not tally:
        vote_msg = f"第{state.round}轮投票：无人得票，平安日。"
        state.public_log.append(vote_msg)
        publish_global(state, vote_msg)
        record_vote(state, no_votes=True)
        logger.info("无人被放逐。")
    else:
        max_votes = max(tally.values())
        top = [pid for pid, c in tally.items() if c == max_votes]
        if len(top) == 1:
            eliminated = top[0]
            eliminate_player(state, eliminated)
            vote_msg = f"第{state.round}轮投票：{eliminated} 号被放逐（得票 {max_votes}）。"
            state.public_log.append(vote_msg)
            publish_global(state, vote_msg)
            record_vote(state, eliminated=eliminated, votes=max_votes)
            logger.info("%s 号玩家被放逐。", eliminated)

            _elimination_last_words(state, eliminated)

            hunter_shoots = resolve_hunter_shoots_for_deaths(
                state, [eliminated], "vote"
            )
            if hunter_shoots:
                header = f"第{state.round}轮：公布猎人技能结果（放逐后）。"
                state.public_log.append(header)
                publish_global(state, header, data_type="system_info")
                announce_hunter_shoots(state, hunter_shoots)
        else:
            tied = "、".join(f"{pid}号" for pid in sorted(top))
            vote_msg = f"第{state.round}轮投票：{tied} 平票，本轮无人被放逐。"
            state.public_log.append(vote_msg)
            publish_global(state, vote_msg)
            record_vote(state, tied_ids=top)
            logger.info("平票（%s），无人被放逐。", tied)

    if check_game_over(state):
        return
    if state.phase != Phase.GAME_OVER:
        state.round += 1
        state.phase = Phase.NIGHT
