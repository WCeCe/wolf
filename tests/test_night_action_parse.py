"""结构化 JSON 宽松解析。"""
import unittest

from schemas.night_action import loads_json_lenient, parse_night_target_decision


class TestNightActionParse(unittest.TestCase):
    def test_parse_markdown_fence(self) -> None:
        raw = '```json\n{"target_id": 4, "reason": "抗推位"}\n```'
        d = parse_night_target_decision(raw, [1, 4, 6])
        self.assertIsNotNone(d)
        self.assertEqual(d.target_id, 4)

    def test_parse_embedded_object(self) -> None:
        raw = '好的，{"target_id": 7, "reason": "像神"}，就他。'
        data = loads_json_lenient(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["target_id"], 7)


if __name__ == "__main__":
    unittest.main()
