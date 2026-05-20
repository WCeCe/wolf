"""5.7 神职私密记忆账本化单元测试。"""
import unittest

from game.models import GameState, Player, Role
from memory.context import build_player_context
from memory.god_consolidation import (
    append_witch_potion_log,
    format_god_private_ledger,
    format_seer_private_ledger,
)
from memory.message import Channel, Message
from memory.selection import select_messages


class TestGodConsolidation(unittest.TestCase):
    def test_seer_ledger_from_history(self) -> None:
        state = GameState()
        state.seer_check_history = [(3, "狼人"), (7, "村民")]
        text = format_seer_private_ledger(state)
        self.assertIn("3号→狼人", text)
        self.assertIn("7号→村民", text)

    def test_discuss_god_no_private_messages(self) -> None:
        private = [
            Message("你查验了 3 号", "system", Channel.PRIVATE, data_type="action"),
        ]
        sel = select_messages(
            role=Role.SEER,
            phase="discuss",
            current_round=2,
            public_memory=[],
            private_memory=private,
            werewolf_memory=[],
            wolf_night_summary=None,
        )
        self.assertEqual(len(sel.private_messages), 0)

    def test_vote_witch_no_private_messages(self) -> None:
        private = [
            Message("你使用解药", "system", Channel.PRIVATE),
            Message("你选择不使用毒药", "system", Channel.PRIVATE),
        ]
        sel = select_messages(
            role=Role.WITCH,
            phase="vote",
            current_round=2,
            public_memory=[],
            private_memory=private,
            werewolf_memory=[],
            wolf_night_summary=None,
        )
        self.assertEqual(len(sel.private_messages), 0)

    def test_build_player_context_injects_seer_ledger(self) -> None:
        state = GameState(round=2)
        state.players[1] = Player(1, "玩家1", Role.SEER)
        state.players[2] = Player(2, "玩家2", Role.VILLAGER)
        state.seer_check_history = [(2, "村民")]
        from memory.memory import PlayerMemory
        from memory.init import init_game_memory

        init_game_memory(state)
        ctx = build_player_context(state, state.players[1], "discuss")
        self.assertIn("预言家私密账本", ctx)
        self.assertIn("2号→村民", ctx)
        self.assertNotIn("你查验了", ctx)

    def test_append_witch_potion_log(self) -> None:
        state = GameState(round=2)
        append_witch_potion_log(
            state,
            round_num=2,
            used_antidote=True,
            wolf_kill_id=5,
            poison_target=None,
            had_antidote_choice=True,
            had_poison_choice=True,
        )
        self.assertEqual(len(state.witch_potion_log), 2)
        self.assertIn("解药救5号", state.witch_potion_log[0])
        self.assertIn("未用毒药", state.witch_potion_log[1])


if __name__ == "__main__":
    unittest.main()
