"""5.1 记忆筛选单元测试。"""
import unittest

from game.models import Role
from memory.message import Channel, Message
from memory.selection import select_messages


def _speech(text: str, round_num: int) -> Message:
    return Message(
        text,
        "1",
        Channel.GLOBAL,
        data_type="speech",
        round=round_num,
    )


def _system(text: str, round_num: int) -> Message:
    return Message(
        text,
        "system",
        Channel.GLOBAL,
        data_type="system_info",
        round=round_num,
    )


class TestMemorySelection(unittest.TestCase):
    def test_villager_vote_keeps_one_round_speech(self):
        public = [
            _system("第1轮死讯", 1),
            _speech("R1发言", 1),
            _speech("R2发言", 2),
            _speech("R3发言", 3),
            _system("第3轮投票前", 3),
        ]
        sel = select_messages(
            role=Role.VILLAGER,
            phase="vote",
            current_round=3,
            public_memory=public,
            private_memory=[],
            werewolf_memory=[],
            wolf_night_summary=None,
        )
        self.assertEqual(len(sel.public_system), 1)
        self.assertEqual(len(sel.public_speech), 1)
        self.assertIn("R3", sel.public_speech[0].content)

    def test_god_night_no_speech(self):
        public = [_system("死讯", 2), _speech("白天", 2)]
        sel = select_messages(
            role=Role.SEER,
            phase="night",
            current_round=2,
            public_memory=public,
            private_memory=[Message("查验3号", "system", Channel.PRIVATE, round=2)],
            werewolf_memory=[],
            wolf_night_summary=None,
        )
        self.assertEqual(len(sel.public_system), 1)
        self.assertEqual(len(sel.public_speech), 0)
        self.assertEqual(len(sel.private_messages), 0)

    def test_werewolf_discuss_uses_summary_not_channel(self):
        sel = select_messages(
            role=Role.WEREWOLF,
            phase="discuss",
            current_round=2,
            public_memory=[_speech("公聊", 2)],
            private_memory=[],
            werewolf_memory=[
                Message("昨晚协商", "2", Channel.WEREWOLF, round=1),
            ],
            wolf_night_summary="第1轮刀口7号",
        )
        self.assertEqual(sel.wolf_summary, "第1轮刀口7号")
        self.assertEqual(len(sel.werewolf_messages), 0)

    def test_non_god_night_returns_empty_selection(self) -> None:
        sel = select_messages(
            role=Role.VILLAGER,
            phase="night",
            current_round=2,
            public_memory=[_system("死讯", 2)],
            private_memory=[],
            werewolf_memory=[],
            wolf_night_summary=None,
        )
        self.assertEqual(sel.public_system, [])
        self.assertEqual(sel.public_speech, [])

    def test_werewolf_channel_tonight_only(self):
        sel = select_messages(
            role=Role.WEREWOLF,
            phase="werewolf_channel",
            current_round=2,
            public_memory=[],
            private_memory=[],
            werewolf_memory=[
                Message("R1夜", "1", Channel.WEREWOLF, round=1),
                Message("R2夜", "2", Channel.WEREWOLF, round=2),
            ],
            wolf_night_summary=None,
        )
        self.assertEqual(len(sel.werewolf_messages), 1)
        self.assertIn("R2", sel.werewolf_messages[0].content)


if __name__ == "__main__":
    unittest.main()
