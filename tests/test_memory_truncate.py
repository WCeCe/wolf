"""5.3 分类型通道截断单元测试。"""
import unittest

from game.models import Role
from memory.memory import PlayerMemory
from memory.message import Channel, Message
from memory.public_split import split_public_messages
from memory.truncate import (
    truncate_private_memory,
    truncate_public_memory,
    truncate_werewolf_memory,
)


def _speech(n: int, text: str = "发言") -> Message:
    return Message(text, str(n), Channel.GLOBAL, data_type="speech", round=1)


def _system(text: str = "死讯") -> Message:
    return Message(text, "system", Channel.GLOBAL, data_type="system_info", round=1)


class TestMemoryTruncate(unittest.TestCase):
    def test_public_keeps_system_drops_old_speech(self):
        messages = [_system(f"s{i}") for i in range(10)]
        messages += [_speech(i, f"sp{i}") for i in range(50)]
        out = truncate_public_memory(messages)
        system, speech = split_public_messages(out)
        self.assertEqual(len(system), 10)
        self.assertEqual(len(speech), 36)
        self.assertEqual(speech[0].content, "sp14")
        self.assertEqual(speech[-1].content, "sp49")

    def test_seer_private_cap_40(self):
        msgs = [
            Message(f"p{i}", "system", Channel.PRIVATE, round=1) for i in range(45)
        ]
        out = truncate_private_memory(msgs, Role.SEER)
        self.assertEqual(len(out), 40)
        self.assertEqual(out[0].content, "p5")

    def test_guard_private_cap_20(self):
        msgs = [Message(f"p{i}", "system", Channel.PRIVATE) for i in range(25)]
        out = truncate_private_memory(msgs, Role.GUARD)
        self.assertEqual(len(out), 20)

    def test_werewolf_channel_cap_64(self):
        msgs = [
            Message(f"w{i}", "1", Channel.WEREWOLF, data_type="speech") for i in range(70)
        ]
        out = truncate_werewolf_memory(msgs, Role.WEREWOLF)
        self.assertEqual(len(out), 64)

    def test_villager_no_werewolf_cap(self):
        msgs = [Message("x", "1", Channel.WEREWOLF) for _ in range(5)]
        out = truncate_werewolf_memory(msgs, Role.VILLAGER)
        self.assertEqual(len(out), 5)

    def test_player_memory_truncate_on_update(self):
        mem = PlayerMemory(1, "预言家")
        mem.public_memory = [_speech(i) for i in range(50)]
        mem.private_memory = [
            Message(f"c{i}", "system", Channel.PRIVATE) for i in range(45)
        ]
        mem.update_from_hub({"global": [], "private": [], "werewolf": []})
        self.assertEqual(len(split_public_messages(mem.public_memory)[1]), 36)
        self.assertEqual(len(mem.private_memory), 40)


if __name__ == "__main__":
    unittest.main()
