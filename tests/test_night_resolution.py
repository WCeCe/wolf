"""夜晚结算：守卫挡刀、女巫救人。"""
import unittest

from game.models import GameState, Player, Role
from game.night_resolution import resolve_night_deaths, wolf_kill_blocked_by


def _minimal_state() -> GameState:
    players = {
        i: Player(player_id=i, name=f"玩家{i}", role=Role.VILLAGER, is_alive=True)
        for i in range(1, 5)
    }
    players[3].role = Role.VILLAGER
    return GameState(players=players, round=2)


class TestNightResolution(unittest.TestCase):
    def test_guard_blocks_wolf_kill(self) -> None:
        state = _minimal_state()
        state.night_actions = {"wolf_kill": 3, "guard_protect": 3}
        deaths = resolve_night_deaths(state)
        self.assertEqual(deaths, [])
        self.assertTrue(state.players[3].is_alive)
        self.assertEqual(wolf_kill_blocked_by(state), "guard")

    def test_witch_save_blocks_death(self) -> None:
        state = _minimal_state()
        state.night_actions = {"wolf_kill": 3, "witch_save": True}
        deaths = resolve_night_deaths(state)
        self.assertEqual(deaths, [])
        self.assertTrue(state.players[3].is_alive)
        self.assertEqual(wolf_kill_blocked_by(state), "witch_save")

    def test_unguarded_wolf_kill_kills(self) -> None:
        state = _minimal_state()
        state.night_actions = {"wolf_kill": 3}
        deaths = resolve_night_deaths(state)
        self.assertEqual(deaths, [3])
        self.assertFalse(state.players[3].is_alive)
        self.assertIsNone(wolf_kill_blocked_by(state))


if __name__ == "__main__":
    unittest.main()
