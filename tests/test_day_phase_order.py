"""白天阶段：死讯公布须先于猎人开枪结算。"""
import unittest
from unittest.mock import MagicMock, patch

from game.models import GameState, Phase, Player, Role
from game.phases.day import day_discussion_phase


class TestDayPhaseOrder(unittest.TestCase):
    @patch("game.phases.day.get_alive_players", return_value=[])
    @patch("game.phases.day.check_game_over", return_value=False)
    @patch("game.phases.day.resolve_hunter_shoots_for_deaths", return_value=[])
    @patch("game.phases.day.record_night_deaths")
    @patch("game.phases.day.resolve_night_deaths", return_value=[7])
    def test_death_announced_before_hunter_resolve(
        self,
        _resolve: MagicMock,
        _record: MagicMock,
        mock_hunter: MagicMock,
        _over: MagicMock,
        _alive: MagicMock,
    ) -> None:
        state = GameState(round=2, phase=Phase.NIGHT)
        state.players[7] = Player(7, "玩家7", Role.HUNTER, is_alive=False)
        order: list[str] = []

        def announce(_state, deaths):
            order.append("announce_deaths")

        def hunter(_state, deaths, cause):
            order.append("hunter_resolve")
            return []

        mock_hunter.side_effect = hunter

        with patch("game.phases.day._announce_night_deaths", side_effect=announce):
            day_discussion_phase(state)

        self.assertEqual(order, ["announce_deaths", "hunter_resolve"])


if __name__ == "__main__":
    unittest.main()
