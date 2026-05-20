"""狼队刀口投票：严格多数与平票决胜。"""
import unittest

from utils.wolf_vote import (
    format_vote_ballot,
    resolve_wolf_kill_vote,
    votes_needed,
)


class TestWolfKillVote(unittest.TestCase):
    def test_votes_needed(self) -> None:
        self.assertEqual(votes_needed(4), 3)
        self.assertEqual(votes_needed(3), 2)
        self.assertEqual(votes_needed(2), 2)
        self.assertEqual(votes_needed(1), 1)

    def test_strict_majority_4_wolves(self) -> None:
        votes = {5: 9, 8: 9, 10: 9, 12: 6}
        r = resolve_wolf_kill_vote(
            votes, [3, 6, 9], [], first_speaker_id=5, wolf_count=4
        )
        self.assertEqual(r.target_id, 9)
        self.assertEqual(r.resolution, "strict_majority")
        self.assertEqual(r.tally[9], 3)

    def test_tie_2_2_first_speaker(self) -> None:
        votes = {5: 9, 8: 6, 10: 6, 12: 9}
        lines = [(5, "刀9号"), (8, "刀6号")]
        r = resolve_wolf_kill_vote(
            votes, [3, 6, 9], lines, first_speaker_id=5, wolf_count=4
        )
        self.assertEqual(r.target_id, 9)
        self.assertEqual(r.resolution, "tie_first_speaker")

    def test_tie_2_2_mentions(self) -> None:
        # 首麦弃权，2:2 平票 → 讨论提及 6 号更多
        votes = {5: None, 8: 6, 10: 9, 12: 6}
        lines = [
            (8, "刀6号"),
            (12, "刀6号"),
            (10, "刀9号"),
        ]
        r = resolve_wolf_kill_vote(
            votes, [6, 9], lines, first_speaker_id=5, wolf_count=4
        )
        self.assertEqual(r.target_id, 6)
        self.assertEqual(r.resolution, "tie_discussion_mentions")

    def test_no_valid_votes_random(self) -> None:
        votes = {5: None, 8: None}
        r = resolve_wolf_kill_vote(
            votes, [3, 6], [], first_speaker_id=5, wolf_count=2
        )
        self.assertIn(r.target_id, [3, 6])
        self.assertEqual(r.resolution, "no_valid_votes_random")

    def test_format_ballot(self) -> None:
        s = format_vote_ballot({5: 9, 8: None, 10: 6})
        self.assertIn("5号→9号", s)
        self.assertIn("8号→弃权", s)


if __name__ == "__main__":
    unittest.main()
