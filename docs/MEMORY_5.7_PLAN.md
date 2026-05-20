# 5.7 神职私密记忆账本化 — 方案大纲与细节

> **状态**：v1 已实现（`memory/god_consolidation.py`、`GameState` 字段、selection 跳过神职 private、`build_player_context` 注入账本）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 **P4**；与 5.1 阶段筛选、5.2 局面账本互补。

---

## 一、总述

### 1.1 要解决的问题（P4）

神职行动结果在 **两处** 进入 LLM：

| 来源 | 内容 |
|------|------|
| `GameState` 结构化字段 | `seer_check_history`、`witch_has_*`、`guard_last_protect` |
| `private_memory` 叙述 | `publish_private` 的「你查验了…」「你使用解药…」等 |

白天讨论/投票时，神职会带上 **整段 private 原文**，与结构化字段 **重复计费**。

夜晚专用 `build_seer/witch/guard_context` 已在 5.1 中让 `phase=night` **不出库 private**；5.7 补齐 **白天** 与 **女巫用药史**。

### 1.2 解决方案（一句话）

**存储仍全量**（`publish_private` 不变）；**出库** 时神职 `private_memory` 置空，改由 **规则生成的私密账本** 从 `GameState` 注入。

### 1.3 不在 5.7 内

| 包含 | 不包含 |
|------|--------|
| 预言家/女巫/守卫白天账本 | 狼人白天狼队频道（→ 5.8） |
| `witch_potion_log` 每夜一行 | 停止 `publish_private` 写入 |
| 猎人私密（专用 `hunter_shoot` 阶段） | 远轮 LLM 摘要（→ 5.9） |

---

## 二、结构化字段与账本格式

### 2.1 预言家

- **字段**：`GameState.seer_check_history: List[(座位, 身份)]`
- **账本**（有记录时）：

```text
【预言家私密账本】以往查验：3号→狼人；7号→村民
```

- **夜晚**：`build_seer_context` 仍含「以往查验记录」+ 本夜可验目标；`selection` 的 `night` 阶段 private 为空。

### 2.2 女巫

- **字段**：`witch_has_antidote` / `witch_has_poison` + **`witch_potion_log`**（每夜 0～2 行）
- **写入**：`roles/witch.py` 当夜决策后 `append_witch_potion_log`
- **账本示例**：

```text
【女巫私密账本】
解药：已用完；毒药：可用
第2轮：解药救5号（狼刀）
第2轮：未用毒药
```

- **夜晚**：`build_witch_context` 仍含当夜刀口与药水状态（不依赖 private）。

### 2.3 守卫

- **字段**：`guard_last_protect`
- **账本**：

```text
【守卫私密账本】上一轮守护：5号(玩家5)（今夜不可再守此人）
```

- **夜晚**：`build_guard_context` 已含同义规则说明。

---

## 三、实现清单

| 文件 | 变更 |
|------|------|
| `memory/god_consolidation.py` | `format_*_private_ledger`、`append_witch_potion_log` |
| `game/models.py` | `witch_potion_log: List[str]` |
| `memory/selection.py` | `discuss`/`vote` 神职 `private_kept=[]`（删除 `_filter_private_for_vote`） |
| `memory/context.py` | `build_player_context` 在记忆块前追加神职账本 |
| `roles/witch.py` | 当夜行动后写 `witch_potion_log` |

---

## 四、验收

- `tests/test_god_consolidation.py`：神职 discuss/vote 无私密 Message 出库；`build_player_context` 含账本且不含「你查验了」类原文。
- `tests/test_memory_selection.py`：`god_night` 仍无私密（5.1 回归）。
- 人工：神职第 3 轮白天发言/投票仍能引用历史查验与用药结果。

---

## 五、风险

| 风险 | 缓解 |
|------|------|
| 账本丢失用药语气细节 | 保留 `publish_private` 供日志；账本只写座位与结果 |
| 女巫 log 与状态不同步 | 仅在 `run_night_camp` 决策落盘后追加 |

---

## 六、相关索引

| 主题 | 路径 |
|------|------|
| 账本格式化 | `memory/god_consolidation.py` |
| 白天上下文 | `memory/context.py` → `build_player_context` |
| 出库筛选 | `memory/selection.py` |
| 总纲 §5.7 | [MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) |
