"""
PlayerMemory：单个玩家的长期记忆仓。

Hub = 未读信箱（fetch 后清空）；
Memory = 已读历史（三层列表，供 get_context_for_llm 格式化给模型）。

5.1：存储仍全量；get_context_for_llm 经 selection 按角色×阶段出库。
"""
from typing import List, Optional

from game.ledger import RoundLedger
from game.models import Role

from .formatter import format_message_block
from .message import Message
from .selection import select_messages
from .truncate import truncate_player_memory

_ROLE_ZH_TO_ENUM = {
    "狼人": Role.WEREWOLF,
    "村民": Role.VILLAGER,
    "预言家": Role.SEER,
    "女巫": Role.WITCH,
    "猎人": Role.HUNTER,
    "守卫": Role.GUARD,
}


class PlayerMemory:
    def __init__(self, player_id: int, role: str):
        self.player_id = player_id
        self.role = role  # 中文，如「狼人」
        self.public_memory: List[Message] = []
        self.private_memory: List[Message] = []
        self.werewolf_memory: List[Message] = []
        self.wolf_night_summary: Optional[str] = None

    def update_from_hub(self, new_messages: dict) -> None:
        """将 fetch_all 结果追加进三层，并执行截断。"""
        self.public_memory.extend(new_messages.get("global", []))
        self.private_memory.extend(new_messages.get("private", []))
        self.werewolf_memory.extend(new_messages.get("werewolf", []))
        self._truncate()

    def _truncate(self) -> None:
        role = self._resolve_role(None)
        pub, priv, wolf = truncate_player_memory(
            role=role,
            public_memory=self.public_memory,
            private_memory=self.private_memory,
            werewolf_memory=self.werewolf_memory,
        )
        self.public_memory = pub
        self.private_memory = priv
        self.werewolf_memory = wolf

    def _resolve_role(self, role: Optional[Role]) -> Role:
        if role is not None:
            return role
        return _ROLE_ZH_TO_ENUM.get(self.role, Role.VILLAGER)

    def get_context_for_llm(
        self,
        phase: str,
        *,
        current_round: int = 1,
        role: Optional[Role] = None,
        round_ledger: Optional[RoundLedger] = None,
    ) -> str:
        """按 5.1 规则筛选三层记忆并格式化为 LLM 可读文本。"""
        role_enum = self._resolve_role(role)
        selected = select_messages(
            role=role_enum,
            phase=phase,
            current_round=current_round,
            public_memory=self.public_memory,
            private_memory=self.private_memory,
            werewolf_memory=self.werewolf_memory,
            wolf_night_summary=self.wolf_night_summary,
            round_ledger=round_ledger,
        )

        parts: List[str] = [f"【当前阶段：{phase}】"]

        if selected.ledger_block:
            parts.append(selected.ledger_block)

        if selected.public_system:
            block = format_message_block(selected.public_system)
            if block:
                parts.append("【公开场面记录】\n" + block)

        if selected.public_speech:
            k = selected.speech_rounds_k
            title = f"【近期公聊（最近{k}轮）】\n" if k else "【近期公聊】\n"
            block = format_message_block(selected.public_speech)
            if block:
                parts.append(title + block)

        if selected.private_messages:
            block = format_message_block(selected.private_messages)
            if block:
                parts.append("【私密信息（仅你可见）】\n" + block)

        if selected.wolf_summary:
            parts.append(f"【狼队战术摘要】\n{selected.wolf_summary}")

        if selected.werewolf_messages:
            block = format_message_block(
                selected.werewolf_messages, werewolf_channel=True
            )
            if block:
                parts.append(f"【本夜狼队频道】\n{block}")

        if len(parts) == 1:
            return ""
        return "\n".join(parts)
