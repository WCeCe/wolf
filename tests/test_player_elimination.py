"""GB-004：出局狼人从 werewolf_ids 移除。"""
import unittest

from game.models import GameState, Player, Role
from game.night_resolution import resolve_night_deaths
from memory.init import init_game_memory
from memory.publish import eliminate_player, on_player_eliminated


class TestPlayerElimination(unittest.TestCase):
    def _state_with_wolves(self) -> GameState:
        state = GameState(round=1)
        state.players[1] = Player(1, "玩家1", Role.WEREWOLF)
        state.players[2] = Player(2, "玩家2", Role.WEREWOLF)
        state.players[3] = Player(3, "玩家3", Role.VILLAGER)
        state.players[4] = Player(4, "玩家4", Role.WITCH)
        init_game_memory(state)
        return state

    def test_on_player_eliminated_removes_dead_wolf(self) -> None:
        state = self._state_with_wolves()
        self.assertIn(1, state.msg_hub.werewolf_ids)
        state.players[1].is_alive = False
        on_player_eliminated(state, 1)
        self.assertNotIn(1, state.msg_hub.werewolf_ids)
        self.assertIn(2, state.msg_hub.werewolf_ids)

    def test_on_player_eliminated_ignores_non_wolf(self) -> None:
        state = self._state_with_wolves()
        before = set(state.msg_hub.werewolf_ids)
        state.players[3].is_alive = False
        on_player_eliminated(state, 3)
        self.assertEqual(state.msg_hub.werewolf_ids, before)

    def test_eliminate_player_idempotent(self) -> None:
        state = self._state_with_wolves()
        self.assertTrue(eliminate_player(state, 1))
        self.assertFalse(eliminate_player(state, 1))
        self.assertNotIn(1, state.msg_hub.werewolf_ids)

    def test_night_death_removes_wolf_from_hub(self) -> None:
        state = self._state_with_wolves()
        state.night_actions["wolf_kill"] = 3
        deaths = resolve_night_deaths(state)
        self.assertEqual(deaths, [3])
        self.assertEqual(state.msg_hub.werewolf_ids, {1, 2})


if __name__ == "__main__":
    unittest.main()
