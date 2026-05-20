"""GB-001：投票放逐遗言。"""
import unittest
from unittest.mock import MagicMock, patch

from game.ledger import RoundLedger, record_last_words
from game.models import GameState, Phase, Player, Role
from game.phases.voting import _elimination_last_words
from memory.init import init_game_memory
from memory.message import Channel, Message
from memory.selection import select_messages


class TestLastWords(unittest.TestCase):
    def test_record_last_words_truncates_long_text(self) -> None:
        state = GameState(round=1)
        state.round_ledger = RoundLedger()
        long_text = "我" * 100
        record_last_words(state, 2, long_text)
        seg = state.round_ledger.segments[1][0]
        self.assertIn("2号遗言", seg)
        self.assertLessEqual(len(seg), 90)

    def test_selection_last_words_like_discuss(self) -> None:
        sel = select_messages(
            role=Role.VILLAGER,
            phase="last_words",
            current_round=2,
            public_memory=[],
            private_memory=[],
            werewolf_memory=[],
            wolf_night_summary=None,
            round_ledger=RoundLedger(),
        )
        self.assertEqual(sel.speech_rounds_k, 2)

    @patch("game.phases.voting.publish_global")
    @patch("game.phases.voting.get_player_handler")
    def test_elimination_publishes_last_words(
        self, mock_get_handler: MagicMock, mock_publish: MagicMock
    ) -> None:
        state = GameState(round=1, phase=Phase.VOTING)
        state.players[2] = Player(2, "玩家2", Role.SEER)
        init_game_memory(state)

        handler = MagicMock()
        handler.last_words.return_value = "我是2号，昨夜验了1号是狼人。"
        mock_get_handler.return_value = handler

        _elimination_last_words(state, 2)

        handler.last_words.assert_called_once()
        self.assertGreaterEqual(mock_publish.call_count, 2)
        speech_calls = [
            c
            for c in mock_publish.call_args_list
            if c.kwargs.get("data_type") == "speech"
        ]
        self.assertEqual(len(speech_calls), 1)
        self.assertIn("1号是狼人", speech_calls[0][0][1])
        segs = state.round_ledger.segments.get(1, [])
        self.assertTrue(any("2号遗言" in s for s in segs), segs)


if __name__ == "__main__":
    unittest.main()
