"""day_discussion_occurred 与狼队频道阶段判断。"""
import unittest

from game.models import GameState
from utils.helpers import (
    has_public_day_speech,
    references_stale_first_night_wording,
)


class TestDayDiscussionFlag(unittest.TestCase):
    def test_flag_true_even_without_memory_speech(self) -> None:
        state = GameState(round=2)
        state.day_discussion_occurred = True
        self.assertTrue(has_public_day_speech(state))

    def test_stale_first_night_wording_detects_首轮(self) -> None:
        self.assertTrue(
            references_stale_first_night_wording("刀3号，首轮出局风险低")
        )
        self.assertFalse(references_stale_first_night_wording("刀3号，中间位可能藏神"))


if __name__ == "__main__":
    unittest.main()
