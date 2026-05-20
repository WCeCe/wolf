"""5.4 生成长度控制（prompt + max_tokens，无写时截断）。"""
import unittest

from config.loader import ConfigLoader
from config.speech_limits import (
    DISCUSS_CHAR_MAX,
    DISCUSS_CHAR_MIN,
    DISCUSS_MAX_TOKENS_DEFAULT,
    discuss_length_instruction,
    max_tokens_for_phase,
)
from llm.speech import werewolf_channel_rules_block
from game.models import GameState


class TestSpeechLimits(unittest.TestCase):
    def test_discuss_length_instruction_range(self) -> None:
        text = discuss_length_instruction()
        self.assertIn(str(DISCUSS_CHAR_MIN), text)
        self.assertIn(str(DISCUSS_CHAR_MAX), text)
        self.assertIn("完整", text)

    def test_load_discuss_action_includes_5_4(self) -> None:
        loader = ConfigLoader()
        prompt = loader.load_action_prompt("discuss", "villager")
        self.assertIn(str(DISCUSS_CHAR_MIN), prompt)
        self.assertIn("我是{player_id}号", prompt)

    def test_max_tokens_for_discuss(self) -> None:
        cfg = {"max_tokens": 500, "discuss_max_tokens": 180}
        self.assertEqual(max_tokens_for_phase(cfg, "discuss"), 180)
        self.assertEqual(max_tokens_for_phase(cfg, "vote"), 500)

    def test_max_tokens_discuss_default(self) -> None:
        self.assertEqual(
            max_tokens_for_phase({"max_tokens": 500}, "discuss"),
            DISCUSS_MAX_TOKENS_DEFAULT,
        )

    def test_loader_merges_discuss_max_tokens_from_profile(self) -> None:
        cfg = ConfigLoader().load_llm_config("villager")
        self.assertEqual(cfg.get("discuss_max_tokens"), 180)
        self.assertEqual(max_tokens_for_phase(cfg, "discuss"), 180)

    def test_werewolf_channel_rules_on_first_night(self) -> None:
        state = GameState(round=1)
        block = werewolf_channel_rules_block(state)
        self.assertIn("【频道须知】", block)
        self.assertIn("还没有白天公聊", block)

    def test_werewolf_channel_rules_after_day(self) -> None:
        from game.models import Player, Role
        from memory.init import init_game_memory
        from memory.message import Channel, Message

        state = GameState(round=2)
        state.players[1] = Player(1, "玩家1", Role.VILLAGER)
        init_game_memory(state)
        state.memories[1].public_memory.append(
            Message("我是1号，先发言。", "1", Channel.GLOBAL, data_type="speech")
        )
        block = werewolf_channel_rules_block(state)
        self.assertIn("【频道须知】", block)
        self.assertNotIn("还没有白天公聊", block)


if __name__ == "__main__":
    unittest.main()
