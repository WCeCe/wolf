"""狼队投票兜底逻辑（无 API）。"""
import unittest

from llm.wolf_vote import vote_target_from_discussion


class TestWolfVoteLlm(unittest.TestCase):
    def test_vote_from_own_discussion_line(self) -> None:
        lines = [
            (9, "我更倾向刀7号，像预言家"),
            (7, "刀4号，先做抗推"),
        ]
        self.assertEqual(vote_target_from_discussion(9, lines, [4, 6, 7]), 7)
        self.assertEqual(vote_target_from_discussion(7, lines, [4, 6, 7]), 4)


if __name__ == "__main__":
    unittest.main()
