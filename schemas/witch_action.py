"""女巫夜晚行动的结构化输出：解药救人 + 毒药。"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json


# poison_target_id=0 表示本夜不使用毒药
POISON_SKIP = 0


@dataclass
class WitchNightDecision:
    use_antidote: bool
    poison_target_id: int  # 0 表示不毒；否则为被毒玩家编号
    reason: str = ""


def build_witch_night_json_schema(poison_candidates: List[int]) -> Dict[str, Any]:
    """
    poison_candidates 应包含 0（不毒）以及可毒杀的存活玩家 id。
    """
    enum_ids = sorted(set([POISON_SKIP] + poison_candidates))
    return {
        "type": "object",
        "properties": {
            "use_antidote": {
                "type": "boolean",
                "description": "是否对今夜狼刀目标使用解药（仅当仍有解药且今夜有人被刀时可为 true）",
            },
            "poison_target_id": {
                "type": "integer",
                "description": "毒药目标玩家编号；0 表示本夜不使用毒药",
                "enum": enum_ids,
            },
            "reason": {
                "type": "string",
                "description": "决策理由，不超过40字",
            },
        },
        "required": ["use_antidote", "poison_target_id", "reason"],
        "additionalProperties": False,
    }


def parse_witch_night_decision(
    raw_json: str,
    poison_candidates: List[int],
    *,
    can_use_antidote: bool,
) -> WitchNightDecision | None:
    try:
        data = json.loads(raw_json)
        use_antidote = bool(data["use_antidote"])
        poison_target_id = int(data["poison_target_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None

    valid_poison = set([POISON_SKIP] + poison_candidates)
    if poison_target_id not in valid_poison:
        return None
    if use_antidote and not can_use_antidote:
        use_antidote = False
    reason = data.get("reason", "")
    if reason is None:
        reason = ""
    return WitchNightDecision(
        use_antidote=use_antidote,
        poison_target_id=poison_target_id,
        reason=str(reason),
    )
