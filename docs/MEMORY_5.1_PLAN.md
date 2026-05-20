# 5.1 阶段感知记忆检索 — 方案大纲与细节

> **状态**：v1 已实现（见 `memory/selection.py`、`memory/memory.py`、`llm/wolf_summary.py`）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 P1 / P3 / P8

---

## 一、总述

### 1.1 要解决的问题

当前 `PlayerMemory.get_context_for_llm` 对 `discuss` / `vote` / `night` 几乎**全量输出**三层记忆，导致：

- 每次 LLM 调用都重复携带远轮公聊原文（P1）；
- 投票、夜晚与讨论使用同一套记忆（P3）；
- 狼人白天额外携带完整狼队频道历史（P8）。

### 1.2 解决方案（一句话）

**存储不变、出库筛选**：Hub → Memory 仍全量追加；仅在拼 LLM context 时，按 **身份 × 阶段 × 消息类型 × 轮次窗口** 筛选子集，再经 `formatter` 输出。

### 1.3 v1 范围（本期要做）

| 包含 | 不包含（后续探讨） |
|------|-------------------|
| 按角色×阶段裁剪公聊 / 私密 / 狼队 | 第 1～K−2 轮公聊 **LLM 远场摘要**（见 §九） |
| `system_info` 讨论/投票/神职夜间 **全量** | 5.2 规则账本、5.4 写入截断、5.5 分层 system |
| 狼队落刀后 **LLM 压成 1 条** 摘要（仅狼人白天/投票） | 远轮摘要粒度实现（已记录偏好：每轮一条列表） |
| `Message.round` 字段 | |

### 1.4 预期收益

- 投票 / 神职夜晚：input token ↓约 **50%～70%**  
- 白天讨论：↓约 **30%～50%**  
- 对局质量：需实现后抽检 3～5 局

---

## 二、原则与边界

### 2.1 核心原则

1. **任务相关**：投票比讨论少带公聊；夜晚不带公聊 `speech`。  
2. **场面全量**：讨论、投票、神职夜间、猎人开枪 — `system_info` **一律全量**（不按轮裁）。  
3. **信息不对称**：村民不见私密/狼队；神职只见自己私密；狼人白天不见狼队原文。  
4. **分场景 system_info**：狼人 `werewolf_channel` / `night_wolf_kill` 使用 **最近 10 条** `system_info`（与白天全量并存）。

### 2.2 存储与出库

```text
publish_* → MsgHub → sync → PlayerMemory（三层全量，可截断上限）
                              ↓
              select_for_llm(role, phase, current_round)  ← 5.1 核心
                              ↓
              format_message_block → build_*_context → LLM
```

- **裁掉** = 本次不进入 prompt，**不删除** Memory 内原文。  
- `discussion_log` / `game.log` 继续完整持久化，供人与复盘。

### 2.3 与 `build_*_context` 的分工

| 信息 | 主要来源 |
|------|----------|
| 存活名单、轮次、身份、候选目标 | `build_*_context` 头部（`GameState`） |
| 预言家查验表、女巫刀口/药水、守卫禁守 | `build_seer/witch/guard_context`（结构化） |
| 死讯、投票、开枪公布 | memory **`system_info` 全量** |
| 公聊推理 | memory **近 K 轮 `speech` 原文** |
| 狼队战术（白天） | memory **LLM 夜间摘要 1 条** |
| 狼队协商（当夜） | memory **当夜 `werewolf` 原文** |

神职 **夜间** memory 段：**不重复贴**已由 `build_*_context` 覆盖的私密长文。

---

## 三、角色与阶段定义

### 3.1 角色（实现按 `Role` 分支，逻辑分组如下）

| 逻辑 | `Role` | 说明 |
|------|--------|------|
| 村民 | `VILLAGER` | 仅 public |
| 预言家 | `SEER` | public + private |
| 女巫 | `WITCH` | public + private |
| 守卫 | `GUARD` | public + private |
| 猎人 | `HUNTER` | **单独策略**（无夜晚 camp，有开枪） |
| 狼人 | `WEREWOLF` | public + 狼队摘要/当夜原文 |

### 3.2 阶段 `phase`

| phase | 调用场景 |
|-------|----------|
| `discuss` | `RoleHandler.discuss` |
| `vote` | `RoleHandler.vote` |
| `night` | `build_seer/witch/guard_context` |
| `hunter_shoot` | `build_hunter_shoot_context` |
| `werewolf_channel` | 狼队频道发言 |
| `night_wolf_kill` | 狼人首领结构化落刀 |

---

## 四、分角色 · 分阶段出库规则（v1 核心表）

**图例**：✓ 进入 LLM context；✗ 本次不输出。

### 4.1 村民

| 阶段 | 必须保留 | 可裁掉 |
|------|----------|--------|
| **讨论** | ✓ `system_info` 全量；✓ 最近 **2** 轮公聊原文 | ✗ >2 轮公聊；✗ 私密；✗ 狼队 |
| **投票** | ✓ `system_info` 全量；✓ 最近 **1** 轮公聊原文 | ✗ >1 轮公聊；✗ 私密；✗ 狼队 |
| **夜间** | 无 LLM | — |

### 4.2 预言家 / 女巫 / 守卫

| 阶段 | 必须保留 | 可裁掉 |
|------|----------|--------|
| **讨论** | ✓ `system_info` 全量；✓ 最近 **2** 轮公聊；✓ **自己 `private` 全部** | ✗ >2 轮公聊；✗ 他人私密；✗ 狼队 |
| **投票** | ✓ `system_info` 全量；✓ 最近 **1** 轮公聊；✓ **投票相关私密**（§4.2.1） | ✗ >1 轮公聊；✗ 无关私密；✗ 狼队 |
| **夜间** | ✓ `system_info` **全量**；结构化技能信息由 `build_*_context` 提供 | ✗ 全部公聊 `speech`；✗ 与 context 重复的私密叙述 |

#### 4.2.1 投票阶段「投票相关私密」

| 身份 | 保留 | 裁掉 |
|------|------|------|
| 预言家 | 所有查验类 `private` | — |
| 女巫 | 药水状态、已用药事实；合并重复条 | 多条「不使用解药/毒药」 |
| 守卫 | — | **全部** `private` |

### 4.3 猎人（单独）

| 阶段 | 必须保留 | 可裁掉 |
|------|----------|--------|
| **讨论** | 同村民：全量 `system_info` + 最近 **2** 轮公聊 | 私密、狼队 |
| **投票** | 同村民：全量 `system_info` + 最近 **1** 轮公聊 | 私密、狼队 |
| **开枪** | ✓ `system_info` 全量；✓ 最近 **2** 轮公聊；可射目标由 `build_hunter_shoot_context` 提供 | 狼队、冗长 `private` |

### 4.4 狼人

| 阶段 | 必须保留 | 可裁掉 |
|------|----------|--------|
| **讨论** | ✓ `system_info` 全量；✓ 最近 **2** 轮公聊；✓ **狼队 LLM 摘要（1 条）**（§五.3） | ✗ 狼队原文；✗ >2 轮公聊 |
| **投票** | ✓ `system_info` 全量；✓ 最近 **1** 轮公聊；✓ **狼队 LLM 摘要（1 条）** | ✗ 狼队原文；✗ >1 轮公聊 |
| **狼队频道** | ✓ `system_info` **近 10 条**；✓ **当夜**狼队原文 | ✗ 公聊 `speech`；✗ 历史轮次狼队记录 |
| **落刀** | ✓ `system_info` 近 10 条；✓ 当夜频道内容；已有摘要（若已生成） | ✗ 公聊 `speech`；✗ 历史狼队 |

---

## 五、横切机制

### 5.1 公聊「最近 K 轮」

- 仅作用于 `data_type == speech` 且公开频道。  
- **讨论 / 猎人开枪 / 狼人讨论**：K = **2**。  
- **投票 / 狼人投票**：K = **1**。  
- 判定：`message.round >= current_round - K + 1`。  
- **第 1～current_round-K-1 轮公聊**：v1 **不展示、不摘要**（直接裁掉）。

### 5.2 `system_info` 全量 vs 近 10 条

| 场景 | `system_info` |
|------|---------------|
| 讨论、投票、神职夜间、猎人开枪、狼人讨论/投票 | **全量** |
| `werewolf_channel`、`night_wolf_kill` | **最近 10 条** |

### 5.3 狼队频道 → LLM 摘要一条（v1 包含）

**时机**：当夜狼队频道结束且 `wolf_kill` 写入后，**每夜 1 次**（全员狼人共用同文案）。

**输入**：当夜 `werewolf_memory` 或 `channel_lines` + 最终刀口。

**输出**：一条中文（建议 ≤120 字），含协商要点与刀口；写入各狼 `private` 或 `PlayerMemory.wolf_night_summary`。

**白天/投票**：只输出该条，**不输出**历史 `werewolf_memory` 全文。

**失败 fallback**：规则拼接 `第{R}轮刀口：{id}号`。

### 5.4 输出格式

仍使用 `memory/formatter.py`：`3号: 内容` / `3号狼队友: 内容`，包在 `<history>` 内。

建议段落标题：

- `【公开场面记录】` — system_info  
- `【近期公聊（最近K轮）】` — speech 子集  
- `【私密信息】` — private 子集（若有）  
- `【狼队战术摘要】` — 狼人白天/投票  
- `【本夜狼队频道】` — 仅 `werewolf_channel` 阶段  

---

## 六、实现概要

### 6.1 模块划分

| 步骤 | 内容 |
|------|------|
| 1 | `Message` 增加 `round: int \| None`；`publish_*` 写入 `state.round` |
| 2 | 新增 `memory/selection.py`：`MemorySelectionPolicy`、`select_messages(...)` |
| 3 | `PlayerMemory.get_context_for_llm(role, phase, current_round, ...)` 调用选择器 |
| 4 | `build_*_context` 传入 `player.role` 与正确 `phase` |
| 5 | `WerewolfHandler` 落刀后 `summarize_wolf_channel()`（LLM，每夜 1 次） |
| 6 | 狼人落刀使用 `night_wolf_kill`，与神职 `night` 策略分离 |

### 6.2 配置常量（可调）

```python
SPEECH_ROUNDS_DISCUSS = 2
SPEECH_ROUNDS_VOTE = 1
SPEECH_ROUNDS_HUNTER_SHOOT = 2
WOLF_SYSTEM_LAST_N = 10
```

### 6.3 实施顺序

1. `Message.round` + publish  
2. 村民 / 神职 / 猎人 `discuss` + `vote`  
3. 神职 `night` + 猎人 `hunter_shoot`  
4. 狼人 `werewolf_channel` + `night_wolf_kill` + LLM 狼队摘要  
5. 日志：每次 LLM 调用记录 `memory_chars` / 估算 token  

---

## 七、验收用例

1. **第 4 轮村民投票**：无第 1～2 轮 `speech`；`system_info` 仍在。  
2. **第 4 轮白天狼人**：有 1 条狼队摘要，无第 1～2 夜 werewolf 长文。  
3. **第 2 夜狼队第 2 只狼发言**：仅当夜 werewolf 原文，无第 1 夜记录。  
4. **第 4 轮女巫投票**：无重复「不使用毒药」；仍有用药/药水状态。  
5. **猎人开枪**：2 轮公聊 + `system_info` 全量。  

---

## 八、风险说明

| 风险 | 缓解 |
|------|------|
| 远轮公聊不可见，模型无法引用早期原话 | v1 接受；后续 §九 远场摘要 |
| 狼队 LLM 摘要失真 | 严格 prompt + 规则 fallback |
| `round` 缺失导致筛选失败 | 发布时强制写入；解析 `第N轮` 兜底 |

---

## 九、后续探讨（不在 v1 实现）

### 9.1 公聊远场 LLM 摘要

当第 K 轮仅展示 K、K−1 轮原文时，第 1～K−2 轮可考虑：

- **本地**：`public_memory` / `discussion_log` **继续全量持久化**；  
- **出库**：用 LLM 对远轮公聊做压缩，再提供给全员。

**已记录的产品偏好**（实现远场时再定稿）：

- 采用 **每轮一条摘要** 的列表（`[R1] …`、`[R2] …`），比合并成一条更清晰，略增 token。  
- 与狼人私密「每夜 1 条」摘要区分：远场摘要为 **公开**、**每轮白天结束后 1 次 LLM**（全员共享，非 12 人各调一次）。

### 9.2 与 5.2 账本的关系

远场若先用规则账本（零 LLM），再升级 LLM 摘要，可 A/B 对比 token 与对局质量。

---

## 十、修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-19 | 纯 5.1 规格；远场摘要列入 §九 |
