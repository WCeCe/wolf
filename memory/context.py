"""
为 LLM 拼接 context 字符串。

引擎在调用 generate_speech / generate_night_action 之前，
应先通过本模块拿到「当前轮次 + 存活名单 + 该玩家记忆」的完整文本。
"""
from typing import TYPE_CHECKING

from utils.helpers import (
    format_discuss_round_hint,
    get_alive_players,
    get_hunter_shoot_candidates,
    get_seer_check_candidates,
    has_public_day_speech,
)
from game.models import Role
from .context_helpers import append_player_memory_block
from .god_consolidation import format_god_private_ledger, format_seer_check_history_body
from .init import sync_player_memory

if TYPE_CHECKING:
    from game.models import GameState, Player


def _format_player_ref(p: "Player") -> str:
    return f"{p.player_id}号({p.name})"


def build_player_context(state: "GameState", player: "Player", phase: str) -> str:
    """
    通用上下文：适用于白天发言、夜晚行动等。

    phase 会传入 PlayerMemory.get_context_for_llm，影响记忆段落标题。
    """
    sync_player_memory(state, player)
    # 使用 get_alive_players 保证座位号升序，与发言/投票阶段一致
    alive = [_format_player_ref(p) for p in get_alive_players(state)]
    lines = [
        f"当前第{state.round}轮。",
        f"你是 {_format_player_ref(player)}，身份：{player.role.value}。",
        "发言或推理时只能以你的座位号自称，不要冒充其他号码。",
        f"存活玩家：{', '.join(alive)}",
    ]
    god_ledger = format_god_private_ledger(state, player.role)
    if god_ledger:
        lines.append(god_ledger)
    if phase == "discuss":
        lines.append(format_discuss_round_hint(state, player))
    append_player_memory_block(state, player, phase, lines)
    return "\n".join(lines)


def build_werewolf_channel_context(state: "GameState", player: "Player") -> str:
    """
    狼队频道专用上下文。

    除记忆外，显式列出队友、可刀目标、已死玩家，减少模型刀错人或对好人说话。
    """
    sync_player_memory(state, player)
    alive_players = get_alive_players(state)
    dead_players = sorted(
        (p for p in state.players.values() if not p.is_alive),
        key=lambda p: p.player_id,
    )

    teammates = [
        p for p in alive_players if p.role == Role.WEREWOLF and p.player_id != player.player_id
    ]
    killable = [p for p in alive_players if p.role != Role.WEREWOLF]

    lines = [
        f"当前第{state.round}轮夜晚。",
        f"你是 {_format_player_ref(player)}，身份：狼人。",
        "【狼队私密频道】仅狼队友可见，好人看不到。请直接和队友商量刀口，不要像在白天对好人发言。",
        f"狼队友：{', '.join(_format_player_ref(p) for p in teammates) or '无（仅剩你一人）'}",
        "严禁建议刀狼队友。",
        f"本轮可刀目标（仅存活好人）：{', '.join(_format_player_ref(p) for p in killable) or '无'}",
    ]
    if dead_players:
        lines.append(
            f"已出局（不可再刀）：{', '.join(_format_player_ref(p) for p in dead_players)}"
        )

    if not has_public_day_speech(state):
        lines.append(
            "【局面】本局尚未进行过任何白天公聊，所有玩家都还没有公开发言或投票。"
            "刀口理由只能基于座位、人数、神职概率猜测或战术偏好（如刀中间位、刀疑似神）；"
            "禁止编造或引用「某人发言如何」「白天表现」「带节奏」「投票倾向」等尚未发生的情节。"
            "可以商量「明天白天怎么演」，但不要声称已经观察到的白天行为。"
        )
    else:
        lines.append(
            "【局面】本局已进行过白天公聊与投票。"
            f"请依据当前第{state.round}轮及下方记忆推理，"
            "刀口理由勿再使用「首夜」「首轮」等指代已过阶段的词语。"
        )

    append_player_memory_block(state, player, "werewolf_channel", lines)
    return "\n".join(lines)


def build_wolf_kill_vote_context(
    state: "GameState",
    player: "Player",
    channel_lines: list[tuple[int, str]],
    killable_ids: list[int],
) -> str:
    """
    狼队刀口投票：仅讨论摘要 + 可刀目标（不拼接长记忆，避免 JSON 截断与多次重试）。
    """
    killable_refs = [
        _format_player_ref(state.players[pid])
        for pid in killable_ids
        if pid in state.players
    ]
    discussion = "\n".join(
        f"  {pid}号狼队友（讨论）: {text}" for pid, text in channel_lines
    ) or "  （无讨论）"

    lines = [
        f"当前第{state.round}轮夜晚 · 狼队刀口投票。",
        f"你是 {_format_player_ref(player)}。",
        "【讨论摘要】",
        discussion,
        f"【可刀目标】{', '.join(killable_refs) or '无'}",
        "【规则】4狼须3票、3狼须2票、2狼须2票；未达门槛按首麦票→讨论热度→随机。",
        "可坚持讨论中的刀口，也可改投；只输出 JSON，不要复述同意刀X。",
    ]
    return "\n".join(lines)


def build_hunter_shoot_context(
    state: "GameState", hunter: "Player", cause: str
) -> str:
    """猎人死亡开枪专用上下文。"""
    sync_player_memory(state, hunter)
    cause_label = "被投票放逐" if cause == "vote" else "昨夜死亡"
    candidates = get_hunter_shoot_candidates(state)
    candidate_refs = [
        _format_player_ref(state.players[pid]) for pid in candidates
    ]

    lines = [
        f"当前第{state.round}轮。",
        f"你是 {_format_player_ref(hunter)}，身份：猎人。",
        f"【猎人开枪】你因{cause_label}即将离场，可发动本局唯一一次开枪。",
        f"可开枪目标（存活玩家）：{', '.join(candidate_refs) or '无'}",
    ]
    append_player_memory_block(state, hunter, "hunter_shoot", lines)
    return "\n".join(lines)


def build_seer_context(state: "GameState", player: "Player") -> str:
    """预言家夜晚专用上下文：强调每夜仅可查验一人，并列出历史查验。"""
    sync_player_memory(state, player)
    alive = [_format_player_ref(p) for p in get_alive_players(state)]
    candidates = get_seer_check_candidates(state, player.player_id)
    candidate_refs = [
        _format_player_ref(state.players[pid]) for pid in candidates
    ]

    lines = [
        f"当前第{state.round}轮夜晚。",
        f"你是 {_format_player_ref(player)}，身份：预言家。",
        "【预言家私密信息】以下仅你可见。",
        "规则：每夜只能查验一名存活玩家（且不能是自己），本夜尚未第二次查验。",
        f"存活玩家：{', '.join(alive)}",
        f"本夜可查验目标：{', '.join(candidate_refs) or '无'}",
    ]
    history = format_seer_check_history_body(state)
    if history:
        lines.append(f"以往查验记录：{history}")
    if state.night_actions.get("seer_check"):
        lines.append("【注意】本夜查验已执行，不可再次查验。")

    append_player_memory_block(state, player, "night", lines)
    return "\n".join(lines)


def build_guard_context(
    state: "GameState",
    player: "Player",
    candidates: list[int],
) -> str:
    """守卫夜晚专用上下文：可选目标、上一轮守护记录。"""
    sync_player_memory(state, player)
    alive = [_format_player_ref(p) for p in get_alive_players(state)]
    candidate_refs = [
        _format_player_ref(state.players[pid]) for pid in candidates
    ]

    lines = [
        f"当前第{state.round}轮夜晚。",
        f"你是 {_format_player_ref(player)}，身份：守卫。",
        "【守卫私密信息】以下仅你可见。",
        "规则：不能守护自己；不能连续两夜守护同一人；守护仅抵挡狼刀，不能防毒药。",
    ]
    if state.guard_last_protect is not None:
        last = state.players[state.guard_last_protect]
        lines.append(
            f"上一轮你守护了：{_format_player_ref(last)}（今夜不可再次守护此人）。"
        )
    else:
        lines.append("上一轮你未守护任何人（或为首夜）。")

    lines.append(f"存活玩家：{', '.join(alive)}")
    lines.append(
        f"今夜可守护目标：{', '.join(candidate_refs) or '无'}"
    )

    append_player_memory_block(state, player, "night", lines)
    return "\n".join(lines)


def build_witch_context(
    state: "GameState",
    player: "Player",
    *,
    wolf_kill_id: int | None,
    can_use_antidote: bool,
    can_use_poison: bool,
) -> str:
    """
    女巫夜晚专用上下文：告知刀口、药水存量，不含其他玩家不应知道的信息。
    """
    sync_player_memory(state, player)
    alive = [_format_player_ref(p) for p in get_alive_players(state)]

    lines = [
        f"当前第{state.round}轮夜晚。",
        f"你是 {_format_player_ref(player)}，身份：女巫。",
        "【女巫私密信息】以下仅你可见。",
        f"解药：{'可用' if can_use_antidote else ('已用完' if not state.witch_has_antidote else '今夜无刀口，无法使用')}",
        f"毒药：{'可用' if can_use_poison else '已用完'}",
    ]
    if wolf_kill_id is not None and wolf_kill_id in state.players:
        target = state.players[wolf_kill_id]
        lines.append(f"今夜狼人刀口：{_format_player_ref(target)}。")
    else:
        lines.append("今夜狼人刀口：未知或无人被刀。")

    lines.append(f"存活玩家：{', '.join(alive)}")
    if can_use_poison:
        poisonable = [
            _format_player_ref(p)
            for p in get_alive_players(state)
            if p.player_id != player.player_id
        ]
        lines.append(f"可毒杀目标：{', '.join(poisonable) or '无'}")

    append_player_memory_block(state, player, "night", lines)
    return "\n".join(lines)
