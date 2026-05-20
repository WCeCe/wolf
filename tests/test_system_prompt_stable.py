"""System prompt 字节级稳定（Prompt Cache 前置条件）。"""
import unittest

from config.loader import PROMPT_TIER_COMPACT, PROMPT_TIER_FULL, ConfigLoader
from game.models import GameState, Player, Role
from llm.speech import werewolf_channel_rules_block
from memory.init import init_game_memory
from memory.message import Channel, Message


class TestSystemPromptStable(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = ConfigLoader()

    def test_same_role_full_identical_across_calls(self) -> None:
        a = self.loader.load_system_prompt("werewolf", PROMPT_TIER_FULL)
        b = self.loader.load_system_prompt("werewolf", PROMPT_TIER_FULL)
        self.assertIs(a, b)

    def test_werewolf_full_unchanged_by_game_state(self) -> None:
        """狼队频道 system 不随是否已有公聊变化（动态规则在 user）。"""
        state_a = GameState(round=1)
        state_b = GameState(round=2)
        state_b.players[1] = Player(1, "玩家1", Role.VILLAGER)
        init_game_memory(state_b)
        state_b.memories[1].public_memory.append(
            Message("我是1号。", "1", Channel.GLOBAL, data_type="speech")
        )
        sys_a = self.loader.load_system_prompt("werewolf", PROMPT_TIER_FULL)
        sys_b = self.loader.load_system_prompt("werewolf", PROMPT_TIER_FULL)
        self.assertEqual(sys_a, sys_b)

    def test_channel_rules_block_differs_before_after_day_speech(self) -> None:
        """频道须知在 user 侧切换，证明不应再拼进 system。"""
        before = werewolf_channel_rules_block(GameState(round=1))
        after_state = GameState(round=2)
        after_state.players[1] = Player(1, "玩家1", Role.VILLAGER)
        init_game_memory(after_state)
        after_state.memories[1].public_memory.append(
            Message("x", "1", Channel.GLOBAL, data_type="speech")
        )
        after = werewolf_channel_rules_block(after_state)
        self.assertIn("还没有白天公聊", before)
        self.assertNotIn("还没有白天公聊", after)

    def test_discuss_and_vote_use_different_tiers(self) -> None:
        full = self.loader.load_system_prompt("seer", PROMPT_TIER_FULL)
        compact = self.loader.load_system_prompt("seer", PROMPT_TIER_COMPACT)
        self.assertNotEqual(full, compact)


if __name__ == "__main__":
    unittest.main()
