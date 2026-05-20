# 5.3 分类型通道上限 — 方案大纲与细节

> **状态**：v1 已实现（`memory/policy_config.py`、`memory/truncate.py`、`PlayerMemory._truncate`）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 P2；与 [MEMORY_5.1_PLAN.md](./MEMORY_5.1_PLAN.md)、[MEMORY_5.2_PLAN.md](./MEMORY_5.2_PLAN.md) 正交。

---

## 一、总述

### 1.1 要解决的问题

`PlayerMemory` 在 `update_from_hub` 后对三层列表做截断。现状：

- 每层统一 **120 条**，不区分 `speech` / `system_info`；
- 公聊 `speech` 涨得快（每轮最多 12 条），易挤占同层里的死讯、投票等 **system_info**；
- 狼人 `werewolf_memory`、预言家 `private_memory` 与村民共用同一逻辑，**高压力角色没有额外仓容**。

**P2**：截断粗糙、上限偏高，极端长局 Memory 体积仍大，且可能先裁掉关键场面信息。

### 1.2 解决方案（一句话）

**按消息类型分桶计数 + 按角色配置上限**：`public_memory` 拆成 `speech` / `system` 两桶；`private`、`werewolf` 按身份给不同 cap；截断时 **优先保留 system、优先裁最旧 speech**。

### 1.3 不在 5.3 内

| 包含 | 不包含 |
|------|--------|
| 本地仓分桶截断 | 出库给 LLM 看多少（→ 5.1） |
| 按角色差异化 `private` / `werewolf` cap | 远轮要点（→ 5.2 账本） |
| 全员统一 `public_*` cap | 单条发言字数 cap（→ 5.4） |
| 截断策略（system 优先） | 用 LLM 压缩 |

### 1.4 与 5.1 / 5.2 的分工

```text
publish → Hub → sync → PlayerMemory 全量追加
                          ↓
                    【5.3】分类型截断（存储层保险丝）
                          ↓
              get_context_for_llm → 【5.1】筛选 + 【5.2】账本
                          ↓
                        LLM
```

- **5.3** 决定「仓里最多留多少条」；**不决定** prompt 里最终展示哪些条。
- 即使 5.1 只出库近 2 轮公聊，仓内仍可能累积更多条；5.3 防止无限增长。

### 1.5 预期收益

- 长局（8 轮+）Memory 列表长度有硬顶，且 **system_info 不易被 speech 挤掉**；
- 狼人狼队频道、预言家私密查验 **更少被误裁**；
- 对单次 LLM input token 影响 **间接、小于 5.1**，主要防极端局与调试时内存膨胀。

---

## 二、设计原则

### 2.1 为何 `public_*` 全员统一

- 12 人收到的 **global 内容相同**（fan-out）；
- 出库已由 5.1（近 K 轮）+ 5.2（远轮账本）控制 token；
- 仅因「狼人」在本地多留几轮公聊，**不会**让 `get_context_for_llm` 多看出 5.1 规定以外的轮次。

故 **`public_speech` / `public_system` 不按角色区分**。

### 2.2 为何 `private` / `werewolf` 按角色区分

| 桶 | 差异来源 |
|----|----------|
| `private` | 预言家查验、女巫用药、守卫守护条数差大；村民几乎为空 |
| `werewolf` | 仅狼人有数据，且多夜频道累积；非狼人该桶恒空 |

### 2.3 截断优先级（同桶内）

1. **分类型**：`public` 拆为 `speech` 与 `system`（`data_type == system_info` 或 `sender == system` → system 桶）。  
2. **超 cap 时**：  
   - `speech`：丢弃 **最旧** 条（`buf` 头部），保留尾部；  
   - `system`：同样 FIFO，但 system 条数少，通常不易触顶；  
   - 若实现「层内总条数」二次保护，**先裁 speech 再裁 system**（system 优先保留）。

### 2.4 `wolf_night_summary` 与截断

- 字段在 `PlayerMemory` 上，**不计入** `werewolf_memory` 条数；
- 落刀后 LLM/规则写入，白天由 5.1 出库，**不受** 5.3 通道 cap 影响。

---

## 三、按角色上限表（v1 定稿）

数值含义（12 人局）：

- `public_speech = 36` ≈ 保留最多 **3 轮** 完整白天发言（3 × 12）；
- `public_system = 80`：死讯/投票/开枪等，远高于实际条数，**实质不裁**；
- `werewolf = 64` ≈ **5～6 夜** 狼队频道（每晚约 4～8 条发言 + 刀口）。

| 角色 | `public_speech` | `public_system` | `private` | `werewolf` |
|------|-----------------|-----------------|-----------|------------|
| 狼人 | 36 | 80 | 20 | **64** |
| 预言家 | 36 | 80 | **40** | —（0，不使用） |
| 女巫 | 36 | 80 | **30** | — |
| 守卫 | 36 | 80 | **20** | — |
| 猎人 | 36 | 80 | **10** | — |
| 村民 | 36 | 80 | **10** | — |

**说明**：

- 非狼人 `werewolf_memory` 列表恒为空，无需配置，实现时对 `Role.WEREWOLF` 才应用 `werewolf` cap。  
- 猎人私密极少，与村民同为 10。  
- 相对「全员同一 private=40」：守卫、村民、猎人仓更紧；狼人 `werewolf` 显著加大。

---

## 四、配置结构（实现参考）

### 4.1 `memory/policy_config.py` 扩展示意

```python
# 全员 public（不按角色）
PUBLIC_SPEECH_CAP = 36
PUBLIC_SYSTEM_CAP = 80

# 按 Role 的 private / werewolf 上限
CHANNEL_CAPS: dict[Role, dict[str, int]] = {
    Role.WEREWOLF: {"private": 20, "werewolf": 64},
    Role.SEER:     {"private": 40},
    Role.WITCH:    {"private": 30},
    Role.GUARD:    {"private": 20},
    Role.HUNTER:   {"private": 10},
    Role.VILLAGER: {"private": 10},
}

DEFAULT_PRIVATE_CAP = 10
```

### 4.2 解析角色

- `PlayerMemory` 构造时传入 `role` 中文名，已有 `_ROLE_ZH_TO_ENUM`；  
- 或 `init_game_memory` 时写入 `PlayerMemory.role_enum: Role` 供截断使用。

### 4.3 截断入口

仅改 `PlayerMemory._truncate()`（及必要时拆为 `_truncate_public` / `_truncate_private` / `_truncate_werewolf`）。

**伪代码**：

```text
update_from_hub:
  extend 三层
  _truncate()

_truncate():
  split public_memory → system[], speech[]
  speech = tail(speech, PUBLIC_SPEECH_CAP)
  system = tail(system, PUBLIC_SYSTEM_CAP)
  public_memory = merge_chronological(system, speech)  # 见 §4.4

  private_memory = tail(private, cap_for_role(role).private)
  if role == WEREWOLF:
    werewolf_memory = tail(werewolf, 64)
```

### 4.4 合并 `public_memory` 顺序

筛选与出库按 `data_type` / `round` 逻辑处理，**不强依赖**列表全序。建议：

- 合并时 **system 在前、speech 在后**（与 `get_context_for_llm` 段落顺序一致）；或  
- 按 `timestamp` 排序后写回（若需严格时间线）。

v1 推荐：**system 块 + speech 块**，实现简单。

---

## 五、触顶场景示例

### 5.1 第 8 轮白天（村民）

- 仓内 `speech` 已达 40+ 条 → 截断为 **36**，丢掉第 1～2 轮最旧发言；  
- `system` 约 20 条 → **不裁**；  
- 5.1 出库仍只带近 2 轮 speech + 5.2 账本 `[R1]…[R6]`。

### 5.2 第 6 夜后（狼人）

- `werewolf_memory` 累计 50 条 → 低于 64，**不裁**；  
- 第 7 夜继续涨，超 64 后裁 **最旧夜晚** 的频道原文（摘要已在 `wolf_night_summary` / 5.1 白天使用）；  
- 当夜 `werewolf_channel` 仍由 5.1 按 `round == current_round` 出库，不依赖被裁掉的历史。

### 5.3 预言家第 10 夜

- `private` 约 10 条查验反馈 → 远低于 40，**不裁**。

---

## 六、实现步骤

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | 增加 `CHANNEL_CAPS` 与 public 常量 | `memory/policy_config.py` |
| 2 | 实现分桶 + 按角色 `_truncate` | `memory/memory.py` |
| 3 | （可选）`PlayerMemory` 保存 `Role` 枚举 | `memory/memory.py`, `memory/init.py` |
| 4 | 单元测试：speech 超 cap 裁旧、system 保留、狼人 werewolf 64 | `tests/test_memory_truncate.py` |
| 5 | 更新 `MEMORY_OPTIMIZATION.md` §5.3 为已实现 | `docs/` |

---

## 七、验收用例

1. **村民 public**：注入 50 条 `speech` + 10 条 `system` → 剩 36 speech + 10 system。  
2. **预言家 private**：注入 45 条 private → 剩 40 条（最旧 5 条丢弃）。  
3. **狼人 werewolf**：注入 70 条 werewolf → 剩 64 条。  
4. **守卫 private**：20 条不裁，45 条裁至 20。  
5. **回归**：现有 `tests/test_memory_selection.py`、`tests/test_ledger.py` 全通过。

---

## 八、风险与说明

| 风险 | 缓解 |
|------|------|
| 裁掉旧 speech 后 5.2 账本未覆盖的细节 | 5.2 已记死讯/投票；跳身份等仍可能丢（接受 v1 范围） |
| public 合并顺序影响极少逻辑 | 出库按 type/round 过滤，弱依赖全序 |
| 与 5.1 重复感 | 5.3 管仓、5.1 管 prompt，职责不同 |

---

## 九、修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-19 | 按角色差异化 private/werewolf；public 全员统一 |
