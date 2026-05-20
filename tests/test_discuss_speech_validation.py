"""白天公聊：不得评价本轮尚未发言的玩家。"""
import unittest

from game.models import GameState, Player, Role
from utils.helpers import (
    format_discuss_round_hint,
    get_current_round_discussion_speakers,
    references_unspoken_players_discussion,
)


class TestDiscussSpeechValidation(unittest.TestCase):
    def test_first_speaker_cannot_attribute_speech_to_others(self) -> None:
        text = "我觉得2号和5号在开局阶段发言过于积极，试图主导节奏。"
        self.assertTrue(
            references_unspoken_players_discussion(text, 1, set(), list(range(1, 13)))
        )

    def test_second_speaker_can_reference_first(self) -> None:
        text = "1号刚才说得对，我怀疑6号。"
        self.assertFalse(
            references_unspoken_players_discussion(text, 2, {1}, list(range(1, 13)))
        )

    def test_second_speaker_cannot_attribute_to_unspoken(self) -> None:
        text = "5号发言太冲，我跟1号的看法一致。"
        self.assertTrue(
            references_unspoken_players_discussion(text, 2, {1}, list(range(1, 13)))
        )

    def test_prior_round_attribution_allowed(self) -> None:
        text = "2号上轮发言诡异，今天先看他的票型。"
        self.assertFalse(
            references_unspoken_players_discussion(text, 3, set(), list(range(1, 13)))
        )

    def test_suspicion_without_speech_claim_ok(self) -> None:
        text = "我怀疑6号是狼，平安夜说明可能有人被救。"
        self.assertFalse(
            references_unspoken_players_discussion(text, 1, set(), list(range(1, 13)))
        )

    def test_get_current_round_speakers_from_log(self) -> None:
        state = GameState(round=1)
        state.discussion_log = [
            "第1轮 · 玩家1：平安夜。",
            "第1轮 · 玩家2：同意。",
        ]
        self.assertEqual(get_current_round_discussion_speakers(state), {1, 2})

    def test_discuss_hint_first_speaker(self) -> None:
        state = GameState(round=1)
        player = Player(player_id=1, name="玩家1", role=Role.VILLAGER)
        hint = format_discuss_round_hint(state, player)
        self.assertIn("第一位发言", hint)
        self.assertIn("尚未开口", hint)


if __name__ == "__main__":
    unittest.main()
