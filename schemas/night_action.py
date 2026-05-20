"""
夜晚行动的结构化输出定义（狼刀、预言家查验等）。

与 llm/night.py 配合：build_night_target_json_schema 约束 API 输出，
parse_night_target_decision 校验并转为 NightTargetDecision。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class NightTargetDecision:
    """LLM 返回的目标玩家决策。"""
    target_id: int
    reason: str = ""


def build_night_target_json_schema(candidates: List[int]) -> Dict[str, Any]:
    """
    OpenAI 兼容的 json_schema（strict）。
    target_id 的 enum 限定为当前合法目标，防止模型 hallucinate 座位号。
    """
    return {
        "type": "object",
        "properties": {
            "target_id": {
                "type": "integer",
                "description": "本回合行动指向的玩家编号",
                "enum": candidates,
            },
            "reason": {
                "type": "string",
                "description": "选择该目标的简短理由，不超过30字",
            },
        },
        "required": ["target_id", "reason"],
        "additionalProperties": False,
    }


def loads_json_lenient(raw: str) -> dict | None:
    """剥离 markdown 代码块并尝试提取 JSON 对象（结构化输出常见脏格式）。"""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def parse_night_target_decision(raw_json: str, candidates: List[int]) -> NightTargetDecision | None:
    """解析 JSON 并校验 target_id 在 candidates 内，非法则返回 None。"""
    data = loads_json_lenient(raw_json)
    if data is None:
        return None
    try:
        target_id = int(data["target_id"])
    except (KeyError, TypeError, ValueError):
        return None
    if target_id not in candidates:
        return None
    reason = data.get("reason", "")
    if reason is None:
        reason = ""
    return NightTargetDecision(target_id=target_id, reason=str(reason))
