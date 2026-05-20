"""狼队频道：发言顺序与跟风检测。"""
import unittest

from game.models import Player, Role
from utils.helpers import is_shallow_wolf_channel_agreement, order_wolves_for_channel
from utils.wolf_channel import build_channel_speak_hint


class TestWolfChannelStrategy(unittest.TestCase):
    def test_shallow_agreement_detected(self) -> None:
        self.assertTrue(is_shallow_wolf_channel_agreement("同意刀9号"))
        self.assertTrue(is_shallow_wolf_channel_agreement("赞同刀9号。"))
        self.assertFalse(
            is_shallow_wolf_channel_agreement("同意刀9号，但白天8号更像预我先刀9")
        )

    def test_order_wolves_differs_by_round(self) -> None:
        wolves = [
            Player(5, "玩家5", Role.WEREWOLF),
            Player(8, "玩家8", Role.WEREWOLF),
            Player(10, "玩家10", Role.WEREWOLF),
            Player(12, "玩家12", Role.WEREWOLF),
        ]
        r1 = [w.player_id for w in order_wolves_for_channel(wolves, 1)]
        r3 = [w.player_id for w in order_wolves_for_channel(wolves, 3)]
        self.assertEqual(sorted(r1), [5, 8, 10, 12])
        self.assertNotEqual(r1, r3)

    def test_first_speaker_hint_requires_proposal(self) -> None:
        hint = build_channel_speak_hint(
            speak_index=0,
            wolf_count=4,
            channel_lines=[],
            killable_ids=[3, 6, 9],
        )
        self.assertIn("首麦", hint)
        self.assertIn("刀X号", hint)

    def test_follow_speaker_hint_forbids_blind_agree(self) -> None:
        hint = build_channel_speak_hint(
            speak_index=1,
            wolf_count=4,
            channel_lines=[(5, "刀9号，夹在中间好抗推")],
            killable_ids=[3, 6, 9],
        )
        self.assertIn("跟麦", hint)
        self.assertIn("禁止只写", hint)
        self.assertIn("5号狼队友", hint)


if __name__ == "__main__":
    unittest.main()
