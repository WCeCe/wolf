"""5.5 分层 system prompt 单元测试。"""
import unittest

from config.loader import PROMPT_TIER_COMPACT, PROMPT_TIER_FULL, ConfigLoader


class TestPromptTier(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = ConfigLoader()

    def test_compact_shorter_than_full(self) -> None:
        for role in ("werewolf", "seer", "villager"):
            full = self.loader.load_system_prompt(role, PROMPT_TIER_FULL)
            compact = self.loader.load_system_prompt(role, PROMPT_TIER_COMPACT)
            self.assertLess(len(compact), len(full) / 3, role)
            self.assertNotIn("【通用高级技巧】", compact)
            self.assertNotIn("核心策略", compact)

    def test_full_includes_advanced_tactics(self) -> None:
        full = self.loader.load_system_prompt("werewolf", PROMPT_TIER_FULL)
        self.assertIn("通用高级技巧", full)

    def test_cache_separates_tiers(self) -> None:
        a = self.loader.load_system_prompt("seer", PROMPT_TIER_FULL)
        b = self.loader.load_system_prompt("seer", PROMPT_TIER_COMPACT)
        self.assertNotEqual(a, b)

    def test_compact_contains_role_and_json_hint(self) -> None:
        compact = self.loader.load_system_prompt("guard", PROMPT_TIER_COMPACT)
        self.assertIn("守卫", compact)
        self.assertIn("JSON", compact)


if __name__ == "__main__":
    unittest.main()
