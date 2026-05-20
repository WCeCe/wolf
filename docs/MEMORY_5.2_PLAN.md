# 5.2 结构化局面账本 — 说明（已实现）

> v1 瘦版：死讯、投票、猎人开枪、开局；**不含**跳身份等公聊解析。  
> 关联：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) §5.2

## 写入时机

| 时机 | 函数 | 示例片段 |
|------|------|----------|
| 开局 | `record_game_start` | `开局12人标准局` |
| 白天公布昨夜死讯前 | `record_night_deaths` | `昨夜3号死亡` / `昨夜平安夜` |
| 投票结束 | `record_vote` | `投票7号被放逐（4票）` / `平票` |
| 猎人公布开枪 | `record_hunter_shoot` | `猎人5号开枪带走8号` |

## 出库（与 5.1）

- 讨论/投票/猎人开枪：`【局面账本】` 展示 `round ≤ current_round − K` 的合并行
- 同轮远场 `system_info` 不再重复输出（近轮 system 仍保留）
- 神职夜间：`include_all_ledger=True`，展示全部账本 + 全量 system

## 代码索引

- `game/ledger.py` — `RoundLedger`、记录与 `format_ledger_block`
- `game/models.py` — `GameState.round_ledger`
- `memory/selection.py` — 拼账本并裁剪 system
- `tests/test_ledger.py`
