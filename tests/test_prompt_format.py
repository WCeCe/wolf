"""5.6 user 消息去重：任务段与局面/记忆分块拼接。"""
import unittest

from config.loader import ConfigLoader
from llm.prompt_format import SCENE_BLOCK_HEADER, build_user_message


class TestPromptFormat(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = ConfigLoader()

    def test_build_user_message_single_context_block(self) -> None:
        task = "你是村民，请投票。"
        ctx = "当前第2轮。\n你是 3号，身份：村民。"
        msg = build_user_message(task, ctx)
        self.assertEqual(msg.count(ctx), 1)
        self.assertIn(SCENE_BLOCK_HEADER, msg)
        self.assertTrue(msg.startswith(task))

    def test_discuss_yaml_has_no_context_placeholder(self) -> None:
        raw = self.loader.load_action_prompt("discuss", "villager")
        self.assertNotIn("{context}", raw)
        self.assertIn("局面与记忆", raw)

    def test_vote_yaml_has_no_context_placeholder(self) -> None:
        raw = self.loader.load_action_prompt("vote", "seer")
        self.assertNotIn("{context}", raw)

    def test_render_then_build_no_duplicate_scene(self) -> None:
        task = self.loader.render_prompt(
            self.loader.load_action_prompt("discuss", "villager"),
            player_id=5,
            player_name="玩家5",
            round=2,
        )
        ctx = "当前第2轮。\n存活玩家：1号, 5号"
        msg = build_user_message(task, ctx)
        self.assertEqual(msg.count("当前第2轮"), 1)
        self.assertEqual(msg.count("存活玩家"), 1)


if __name__ == "__main__":
    unittest.main()
