"""5.2 局面账本单元测试。"""
import unittest

from game.ledger import (
    RoundLedger,
    format_ledger_block,
    ledger_max_round_for_context,
    record_night_deaths,
    record_vote,
)
from game.models import GameState
from memory.message import Channel, Message
from memory.selection import select_messages
from game.models import Role


class TestRoundLedger(unittest.TestCase):
    def test_merge_segments_per_round(self):
        ledger = RoundLedger()
        ledger.add(2, "昨夜3号死亡")
        ledger.add(2, "投票7号被放逐（4票）")
        lines = ledger.lines_up_to(2)
        self.assertEqual(len(lines), 1)
        self.assertIn("昨夜3号死亡", lines[0])
        self.assertIn("投票7号被放逐", lines[0])

    def test_ledger_max_round_for_discuss(self):
        self.assertEqual(ledger_max_round_for_context(5, 2), 3)
        self.assertEqual(ledger_max_round_for_context(5, 1), 4)

    def test_format_ledger_block(self):
        ledger = RoundLedger()
        ledger.add(1, "开局12人")
        ledger.add(2, "昨夜平安夜")
        text = format_ledger_block(ledger, current_round=4, speech_rounds_k=2)
        self.assertIn("【局面账本", text)
        self.assertIn("[R1]", text)
        self.assertIn("[R2]", text)
        self.assertNotIn("[R3]", text)

    def test_record_on_state(self):
        state = GameState()
        state.round = 2
        record_night_deaths(state, [3])
        record_vote(state, eliminated=7, votes=4)
        lines = state.round_ledger.lines_up_to(2)
        self.assertEqual(len(lines), 1)
        self.assertIn("昨夜3号死亡", lines[0])
        self.assertIn("投票7号被放逐", lines[0])

    def test_selection_includes_ledger_excludes_old_system(self):
        ledger = RoundLedger()
        ledger.add(1, "昨夜2号死亡")
        ledger.add(2, "投票3号被放逐（5票）")
        public = [
            Message("第1轮死讯", "system", Channel.GLOBAL, data_type="system_info", round=1),
            Message("R1发言", "1", Channel.GLOBAL, data_type="speech", round=1),
            Message("第3轮死讯", "system", Channel.GLOBAL, data_type="system_info", round=3),
            Message("R3发言", "3", Channel.GLOBAL, data_type="speech", round=3),
        ]
        sel = select_messages(
            role=Role.VILLAGER,
            phase="discuss",
            current_round=3,
            public_memory=public,
            private_memory=[],
            werewolf_memory=[],
            wolf_night_summary=None,
            round_ledger=ledger,
        )
        self.assertIn("[R1]", sel.ledger_block)
        # round 3 discuss k=2: 保留 round>=2 的 speech，仅有 R3
        self.assertEqual(len(sel.public_speech), 1)
        self.assertIn("R3", sel.public_speech[0].content)
        system_rounds = [
            m for m in sel.public_system if m.round is not None
        ]
        self.assertTrue(all(m.round >= 2 for m in system_rounds))


if __name__ == "__main__":
    unittest.main()
