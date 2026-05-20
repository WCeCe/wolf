"""
5.1～5.3、5.5～5.7 行为契约验收（策略不变，防回归）。

每项对应 MEMORY_OPTIMIZATION.md 一节；失败即表示出库/拼接策略被破坏。
"""
import unittest

from config.loader import PROMPT_TIER_COMPACT, PROMPT_TIER_FULL, ConfigLoader
from game.ledger import RoundLedger
from game.models import GameState, Player, Role
from memory.context import build_player_context
from memory.init import init_game_memory
from memory.memory import PlayerMemory
from memory.message import Channel, Message
from memory.policy_config import (
    SPEECH_ROUNDS_DISCUSS,
    SPEECH_ROUNDS_VOTE,
    WOLF_SYSTEM_LAST_N,
)
from memory.selection import select_messages
from memory.truncate import truncate_public_memory


class TestMemoryAcceptance(unittest.TestCase):
    def test_5_1_speech_window_constants(self) -> None:
        self.assertEqual(SPEECH_ROUNDS_DISCUSS, 2)
        self.assertEqual(SPEECH_ROUNDS_VOTE, 1)
        self.assertEqual(WOLF_SYSTEM_LAST_N, 10)

    def test_5_1_wolf_daytime_summary_only(self) -> None:
        sel = select_messages(
            role=Role.WEREWOLF,
            phase="discuss",
            current_round=3,
            public_memory=[],
            private_memory=[],
            werewolf_memory=[Message("旧频道", "1", Channel.WEREWOLF, round=1)],
            wolf_night_summary="第2轮刀口5号",
        )
        self.assertEqual(sel.wolf_summary, "第2轮刀口5号")
        self.assertEqual(sel.werewolf_messages, [])

    def test_5_2_ledger_covers_old_rounds_on_discuss(self) -> None:
        ledger = RoundLedger()
        ledger.add(1, "昨夜3号死亡")
        ledger.add(2, "投票5号被放逐")
        sel = select_messages(
            role=Role.VILLAGER,
            phase="discuss",
            current_round=3,
            public_memory=[],
            private_memory=[],
            werewolf_memory=[],
            wolf_night_summary=None,
            round_ledger=ledger,
        )
        self.assertIn("[R1]", sel.ledger_block)
        self.assertIn("3号死亡", sel.ledger_block)

    def test_5_3_public_split_then_cap(self) -> None:
        msgs = [
            Message("s", "system", Channel.GLOBAL, data_type="system_info"),
            Message("sp", "1", Channel.GLOBAL, data_type="speech"),
        ]
        truncated = truncate_public_memory(msgs * 50)
        system, speech = [], []
        for m in truncated:
            (speech if m.data_type == "speech" else system).append(m)
        self.assertLessEqual(len(speech), 36)
        self.assertLessEqual(len(system), 80)

    def test_5_5_compact_shorter_than_full(self) -> None:
        loader = ConfigLoader()
        full = loader.load_system_prompt("seer", PROMPT_TIER_FULL)
        compact = loader.load_system_prompt("seer", PROMPT_TIER_COMPACT)
        self.assertLess(len(compact), len(full))
        self.assertNotIn("核心策略", compact)

    def test_5_7_god_discuss_uses_ledger_not_private_narrative(self) -> None:
        state = GameState(round=2)
        state.players[1] = Player(1, "玩家1", Role.SEER)
        state.players[2] = Player(2, "玩家2", Role.VILLAGER)
        state.seer_check_history = [(2, "村民")]
        init_game_memory(state)
        mem = state.memories[1]
        mem.private_memory = [
            Message("你查验了 2 号，身份是：村民", "system", Channel.PRIVATE),
        ]
        ctx = build_player_context(state, state.players[1], "discuss")
        self.assertIn("预言家私密账本", ctx)
        self.assertIn("2号→村民", ctx)
        self.assertNotIn("你查验了", ctx)
        self.assertNotIn("【私密信息", ctx)

    def test_5_7_god_night_still_no_private_channel(self) -> None:
        sel = select_messages(
            role=Role.WITCH,
            phase="night",
            current_round=2,
            public_memory=[Message("死讯", "system", Channel.GLOBAL, data_type="system_info")],
            private_memory=[Message("用药", "system", Channel.PRIVATE)],
            werewolf_memory=[],
            wolf_night_summary=None,
            round_ledger=RoundLedger(),
        )
        self.assertEqual(sel.private_messages, [])
        self.assertGreater(len(sel.public_system), 0)


if __name__ == "__main__":
    unittest.main()
