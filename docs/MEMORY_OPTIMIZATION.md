# 记忆系统优化大纲

> 本文档描述 Agent-Werewolf 当前记忆架构、各场景下送入大模型的内容，以及分阶段优化方案。  
> 每个优化项均标注其针对的具体问题编号（P1～P8）。

---

## 1. 现有记忆系统概览

### 1.1 设计目标

- **Hub（信箱）**：事件发生后广播，玩家行动前 `fetch` 并清空个人队列（fan-out，避免多人抢同一队列）。
- **Memory（已读仓）**：每个玩家三层列表，持久保留本局已读历史，供拼 LLM `context`。
- **与 `GameState.public_log` 的区别**：`public_log` / `discussion_log` 仅人类日志与调试，**不参与** LLM 上下文；模型所见信息一律经 `publish_*` → Hub → Memory。

### 1.2 核心组件

| 模块 | 文件 | 职责 |
|------|------|------|
| 消息体 | `memory/message.py` | `Message`（content, sender, channel, data_type） |
| 消息中心 | `memory/msg_hub.py` | 按玩家分队列广播 / `fetch_all` |
| 玩家记忆 | `memory/memory.py` | `PlayerMemory` 三层列表 + 截断 + `get_context_for_llm` |
| 格式化 | `memory/formatter.py` | `3号: 内容` + `<history>...</history>` 包裹 |
| 发布入口 | `memory/publish.py` | `publish_global` / `publish_private` / `publish_werewolf` |
| 生命周期 | `memory/init.py` | `init_game_memory`、`sync_player_memory` |
| 上下文拼接 | `memory/context.py` | `build_*_context` 组合局面信息 + 记忆 |

### 1.3 三层记忆频道

| 层级 | 对应 Hub 队列 | 谁写入 | 典型内容 |
|------|---------------|--------|----------|
| `public_memory` | `global` | 全员 | 开局公告、死讯、白天发言、投票结果、猎人开枪公布 |
| `private_memory` | `private` | 指定玩家 | 预言家查验结果、女巫用药反馈、守卫守护记录、猎人私密开枪 |
| `werewolf_memory` | `werewolf` | 仅狼人 | 狼队频道协商发言、刀口公告 |

### 1.4 时序（单次 LLM 调用前）

```
游戏事件 publish_* → MsgHub 各玩家队列
        ↓
某玩家即将行动 → sync_player_memory(player)
        ↓
fetch_all → update_from_hub → 追加到三层 Memory → _truncate（每层最多 120 条）
        ↓
build_*_context → get_context_for_llm(phase) → 拼入 user 消息
        ↓
llm/* 调用（system prompt + user message）
```

### 1.5 当前截断策略

- 常量：`_MAX_PER_CHANNEL = 120`（`memory/memory.py`）
- 策略：每层超过 120 条时 **丢弃最旧消息**（尾部保留），无摘要、无按类型区分。
- 代码内 TODO：上下文紧张时应改为摘要压缩，尚未实现。

### 1.6 `data_type` 分类（写入时）

| data_type | 含义 | 典型来源 |
|-----------|------|----------|
| `system_info` | 系统场面信息 | 死讯、投票、开局、猎人公告 |
| `speech` | 玩家发言 | 白天公聊、狼队频道 |
| `action` | 私密行动反馈 | 女巫用药、守卫守护 |

> **现状问题**：`get_context_for_llm` 对 `data_type` **几乎不做过滤**（仅 `werewolf_channel` 阶段对 public 取最近 10 条 `system_info`），白天讨论/投票会带上全部类型的 public 历史。

---

## 2. 哪些内容会写入记忆（事件源）

### 2.1 公开频道 `publish_global`

| 触发位置 | 内容示例 | data_type |
|----------|----------|-----------|
| `memory/init.py` | 开局在场玩家列表 | system_info |
| `game/phases/day.py` | 昨夜死讯 / 平安夜 | system_info |
| `game/phases/day.py` | 每名存活玩家白天发言全文 | speech（sender=座位号） |
| `game/phases/voting.py` | 投票结果、放逐、平票 | system_info |
| `roles/hunter.py` | 猎人开枪、无法开枪等公布 | system_info |

### 2.2 私密频道 `publish_private`

| 触发位置 | 接收者 | 内容示例 |
|----------|--------|----------|
| `roles/seer.py` | 预言家 | 查验 X 号是狼人/好人 |
| `roles/witch.py` | 女巫 | 用药 / 不用药 |
| `roles/guard.py` | 守卫 | 今夜守护了谁 |
| `roles/hunter.py` | 猎人 | 开枪带走了谁（含身份） |

### 2.3 狼队频道 `publish_werewolf`

| 触发位置 | 内容 |
|----------|------|
| `roles/werewolf.py` | 每名狼人当夜频道发言全文 |
| `roles/werewolf.py` | 最终刀口公告 |

### 2.4 已在 `GameState` 但重复出现在记忆中的信息

| 字段 | 说明 |
|------|------|
| `seer_check_history` | 预言家上下文已单独列出，但 `private_memory` 仍保留每次查验原文 |
| `witch_has_antidote/poison` | 女巫上下文已列药水状态，`private_memory` 仍有用药叙述 |
| `guard_last_protect` | 守卫上下文已列上轮守护，私密记忆仍有重复 |
| `night_actions` | 当夜决策；白天死讯又以 `system_info` 进入 public |

---

## 3. 送入大模型的完整载荷（按场景）

每次调用 = **`system` 消息** + **`user` 消息**。下表描述 **user 侧** 中与记忆相关的部分（不含 JSON schema 等结构化附加约束）。

### 3.1 通用拼接：`build_player_context`（白天发言 / 投票 / 狼人结构化刀人）

```
当前第{R}轮。
你是 {N}号(玩家N)，身份：{角色}。
发言或推理时只能以你的座位号自称……
存活玩家：1号(玩家1), 2号(玩家2), …

【当前阶段：discuss|vote|night】
【私密信息（仅你可见）】     ← private_memory 全部（若有）
【狼队频道记录】             ← werewolf_memory 全部（仅狼人）
【公开讨论与场面记录】       ← public_memory 全部（若有）
```

记忆块经 `format_message_block` 格式化为：

```text
<history>
系统: 第1轮：昨夜 3 号玩家死亡。
3号: 我是3号，我觉得……
…
</history>
```

**5.6 已实现**：action 模板不再嵌入 `{context}`；由 `llm/prompt_format.build_user_message` 在 task 后以 `【局面与记忆】` 块 **只拼接一次**（见 [MEMORY_5.6_PLAN.md](./MEMORY_5.6_PLAN.md)）。

### 3.2 狼队频道：`build_werewolf_channel_context` + `generate_werewolf_channel_speech`

除局面信息（队友、可刀目标、已死玩家、首夜约束）外，记忆为：

```
【当前阶段：werewolf_channel】
【本局狼队频道历史】           ← werewolf_memory 全部
【公开场面信息（死讯等）】     ← public 中仅 system_info 最近 10 条
```

**5.6 已实现**：狼队频道与讨论相同，仅通过 `build_user_message` 追加一次局面块，不再二次粘贴。

每夜 4 狼 × 至少 1 次调用；校验失败时 **整段 context 再打一次**（见 P7）。

### 3.3 预言家夜晚：`build_seer_context`

```
轮次、身份、规则说明
存活玩家、本夜可查验目标
以往查验记录：{seer_check_history 拼接}    ← 结构化重复
【注意】本夜已查验…

+ get_context_for_llm("night")  → 私密 + 狼队(无) + public 全文
```

### 3.4 女巫夜晚：`build_witch_context`

```
轮次、身份、解药/毒药状态、今夜刀口、存活/可毒目标

+ get_context_for_llm("night")  → 含大量与上文重复的 private 用药记录
```

### 3.5 守卫夜晚：`build_guard_context`

```
轮次、身份、规则、上轮守护、可守护目标

+ get_context_for_llm("night")
```

### 3.6 猎人开枪：`build_hunter_shoot_context`

```
轮次、身份、出局原因、可射杀目标

+ get_context_for_llm("discuss"|"vote")  → 往往含极长 public 发言史
```

### 3.7 结构化投票 / 夜晚刀查验：`generate_vote` / `generate_night_action`

- **system**：完整 `load_system_prompt(role_key)`（与人设小作文同长，见 P5）
- **user**：`build_*_context` 全文 + action prompt + JSON 约束

失败时可能再走 `generate_player_response` **第二次完整调用**。

### 3.8 System Prompt（每次调用都带）

来源：`config/prompts/system/{role_key}.yaml`，例如狼人含大段「核心策略 / 伪装层次 / 独立观察」等，**与当前阶段无关**，投票与结构化夜晚行动同样携带全文。

### 3.9 单局 LLM 调用量级（12 人标准局，粗算）

| 阶段 | 每轮约调用次数 | 记忆随轮次 |
|------|----------------|------------|
| 狼队频道 | 4～8（含重试） | 当夜递增，历史轮次狼队发言累积 |
| 预/女/守/刀 | 4～5 | public + private 持续增长 |
| 白天发言 | ≤12 | public 增加 12 条 speech |
| 投票 | ≤12 | 同上，且 context 与发言阶段类似 |

**总 token ≈ Σ(每次调用的 system + user input + output)**。轮次越深，**每次**调用的 input 越长（P1、P2）。

---

## 4. 问题清单（现状痛点）

| 编号 | 问题 | 表现 |
|------|------|------|
| **P1** | **记忆随轮次线性膨胀，且每次调用全量注入** | 第 5 轮白天第 10 号发言仍携带第 1～4 轮全部公聊原文 |
| **P2** | **截断上限过高且策略粗糙** | 120 条/层才丢弃；早期关键信息（如首验）可能被裁掉而非压缩 |
| **P3** | **阶段不敏感** | 投票/夜晚行动不需要完整发言史，但仍注入 `discuss` 级 public |
| **P4** | **结构化状态与叙述记忆重复** | `seer_check_history`、药水状态、守护记录与 private 原文双份 |
| **P5** | **System Prompt 过重且不分场景** | 结构化 vote/night 也携带完整人设长文 |
| **P6** | **Context 在模板中重复拼接** | `build_*_context` 已含局面+记忆，`discuss.yaml` / 狼队 speech 再次嵌入 |
| **P7** | **狼队频道重试加倍成本** | 校验失败时同 context 再调一次 LLM |
| **P8** | **狼人白天负担最重** | public + werewolf + private 三层全量；狼队历史对白天伪装价值递减 |

---

## 5. 优化方案（分项 + 针对问题）

### 5.1 阶段感知记忆检索（Phase-Aware Retrieval）

> **完整大纲与实现细节（v1）**：[MEMORY_5.1_PLAN.md](./MEMORY_5.1_PLAN.md)  
> v1：**纯裁剪**（远轮公聊不展示、不做远场 LLM 摘要）；狼人白天使用 **落刀后 LLM 狼队摘要 1 条**。  
> **后续**：公聊远场拟采用 **每轮一条摘要列表**（见该文档 §九），待 v1 跑通后再做。

**概要**

- 存储全量，出库时按 **身份 × 阶段** 筛选（村民 / 预女守 / 猎人 / 狼人规则不同）。
- 讨论：`system_info` 全量 + 最近 **2** 轮公聊原文；投票：全量 + 最近 **1** 轮。
- 神职夜间：`system_info` 全量 + `build_*_context` 结构化字段，不带公聊 speech。
- 狼人白天：全量 system + 近场公聊 + **狼队 LLM 摘要 1 条**（不带狼队原文）；狼队频道：当夜原文。

**针对**：P1、P3、P8  

**预期**：投票/夜晚 input 降 **50%～70%**；白天降 **30%～50%**。

---

### 5.2 结构化游戏账本（Round Ledger）

> **已实现**：`game/ledger.py`、`GameState.round_ledger`；在 `init` / `day` / `voting` / 猎人公布时写入；`memory/selection` 出库时输出 `【局面账本】` 并去重远轮 `system_info`。

**做法**

- `GameState.round_ledger`（`RoundLedger`）按轮合并要点，例如：`[R2] 昨夜3号死亡；投票7号被放逐（4票）`
- 来源：死讯、投票、猎人开枪等 **规则生成**，无需 LLM
- 与 5.1 配合：公聊保留最近 K 轮时，账本展示 **round ≤ current_round − K** 的条目；近轮仍用 speech / system 原文

**针对**：P1、P2、P4  

**预期**：轮次增加时 context 长度 **亚线性**；避免截断误删首验等关键信息。

---

### 5.3 分类型通道上限（Typed Channel Caps）

> **完整大纲与实现细节**：[MEMORY_5.3_PLAN.md](./MEMORY_5.3_PLAN.md)（已实现）

**概要**

- **存储层**保险丝：在 `PlayerMemory._truncate` 按 **消息类型分桶**，不再三层共用 120 条。
- **`public_speech` / `public_system`**：全员统一（36 / 80）；**`private` / `werewolf`**：按角色配置（狼人 werewolf **64**，预言家 private **40**，等）。
- 超 cap 时：**优先裁最旧 speech，尽量保留 system_info**。
- 与 5.1（出库）、5.2（账本）正交；不增加 LLM 调用。

**针对**：P2  

**预期**：长局 Memory 有硬顶；狼队频道与神职私密更少被误裁。

---

### 5.4 白天公聊生成长度控制（Prompt + max_tokens）✅

> **完整大纲与实现细节**：[MEMORY_5.4_PLAN.md](./MEMORY_5.4_PLAN.md)（v1 已实现）

**概要（C 方案：生成时控长，无写时截断）**

- **主路径**：`discuss.yaml` 角色语气 + `discuss_length_instruction()`（约 **120～180 字、一段完整公聊**）。
- **硬上限**：`discuss_max_tokens`（默认 180），与篇幅指引对齐；**不**在 `publish_*` 砍入库内容。
- **风格**：仍用 **full system**；长度约束在 action task，不改为 compact。
- **附带**：狼队频道动态规则移入 user `【频道须知】`，`system` 仅 full 人设（利于 Prompt Cache）；`werewolf_channel_max_tokens` 默认 100。
**针对**：P1（单条过长）、P7（间接减少重试 context 体积）  

**预期**：单条 speech 体积可控；远轮拼入 user 的 token 下降；体验保持「完整一段话」。

---

### 5.5 分层 System Prompt（Tiered System Prompt）

> **完整大纲与实现细节**：[MEMORY_5.5_PLAN.md](./MEMORY_5.5_PLAN.md)（已实现）

**概要**

- 人设 `system/{role}.yaml` + `advanced_tactics` 过长，且 **投票/夜晚结构化** 与 **白天发言** 共用全文。
- 按场景选 **`full`**（扮演、狼队频道）或 **`compact`**（投票、刀/验/守、女巫、猎人开枪）：compact 仅身份 + 硬规则 + 输出提示，**不**带 strategy 长文与 advanced_tactics。
- 实现：`load_system_prompt(role, tier)` + `config/prompts/system/{role}_compact.yaml`。

**针对**：P5  

**预期**：结构化调用 system input 降 **60%～80%**；发言质量不变。

---

### 5.6 去除 Context 重复拼接（De-duplication）✅

**状态**：v1 已实现。详见 [MEMORY_5.6_PLAN.md](./MEMORY_5.6_PLAN.md)。

**做法**

- `discuss.yaml` / `vote.yaml` / `hunter_shoot.yaml`：task 不再含 `{context}`；instruction 指向「下方【局面与记忆】」。
- `llm/prompt_format.build_user_message`：`client` / `speech` / `vote` / `night` / `hunter` / `witch` 统一拼接。
- 夜晚/猎人：去掉与 `build_*_context` 重复的 `你是 X 号` 前缀或第二块局面粘贴。

**针对**：P6  

**预期**：每次调用 user 侧减少 **10%～25%** 重复 token。

---

### 5.7 私密记忆账本化（Private Memory Consolidation）✅

**状态**：v1 已实现。详见 [MEMORY_5.7_PLAN.md](./MEMORY_5.7_PLAN.md)。

**做法**

- 预言家：白天由 `seer_check_history` 生成【预言家私密账本】；`private_memory` 查验原文不出库。
- 女巫：`witch_has_*` + `witch_potion_log` 每夜一行；夜晚仍用 `build_witch_context` 刀口/药水。
- 守卫：`guard_last_protect` 生成【守卫私密账本】；历史守护叙述不出库。

**针对**：P4  

**预期**：神职白天/夜晚 context 再降 **20%～40%**（相对双份结构化+叙述）。

---

### 5.8 狼队记忆与白天解耦（Werewolf Daytime Decoupling）— 已由 5.1 覆盖，无需单独做

**结论**：不必再开 5.8 工程项。你记得的「狼队频道压缩」就是 5.1 §5.3 已落地能力。

**现状（`memory/selection.py` + `llm/wolf_summary.py`）**

| 阶段 | 狼人看到什么 |
|------|----------------|
| `werewolf_channel` / `night_wolf_kill` | 当夜频道原文（`_filter_werewolf_tonight`）+ 落刀后可选摘要 |
| `discuss` / `vote` | **仅** `【狼队战术摘要】`（`PlayerMemory.wolf_night_summary`，每夜 LLM 一条，含协商要点与刀口）；**不**出库历史 `werewolf_memory` 全文 |

落刀后 `summarize_wolf_channel` → `apply_wolf_night_summary`（见 `roles/werewolf.py`），与 5.8 草案里「写一条私密摘要」效果等价，只是字段在 `wolf_night_summary` 而非 `private_memory`。

**若白天仍觉得「不知道队友想干什么」**：应调摘要 prompt/字数或 fallback 规则，**不要**恢复白天灌整段频道——那会把 P8 的 token 问题带回来。仓内仍保留最多 64 条频道原文（5.3 截断），仅供当夜协商阶段使用。

**针对**：P8（已通过 5.1 缓解）

---

### 5.9 轮次摘要压缩（LLM Summarization，可选 P2 阶段）

**做法**

- 每轮 **投票结束后**，对每个玩家或仅 public 频道调用一次 LLM，生成 ≤150 字「第 N 轮摘要」，写入 `round_summaries[N]`。
- `get_context_for_llm`：`轮次 < 当前-2` 用摘要；近 2 轮保留 speech 原文。

**针对**：P1、P2（长线局截断仍不够时）  

**代价**：每轮 +1 次 LLM 调用；摘要可能丢失语气、欺骗细节（**狼人局需谨慎**）。  

**建议**：在 5.1～5.8 完成后再评估是否需要。

---

### 5.10 狼队重试策略优化（Retry Policy）

**做法**

- 重试时 user 消息只追加 **短纠错指令**，不重复完整 `ctx`；或第二次改用更短 template。
- 写入前本地规则裁剪明显违规句，减少重试率。

**针对**：P7  

**预期**：狼队频道 token **接近减半**（重试场景）。

---

## 6. 实施路线图

### 阶段 A（低成本，建议先做）

| 序号 | 项 | 方案节 | 主要解决问题 |
|------|-----|--------|----------------|
| A1 | 阶段感知 `get_context_for_llm` | 5.1 | P1, P3 |
| A2 | 白天公聊生成长度控制 ✅ | 5.4 | P1 |
| A3 | 分类型通道上限 | 5.3 | P2 |
| A4 | 去除 context 重复拼接 ✅ | 5.6 | P6 |
| A5 | 狼人白天不注入完整 werewolf_memory ✅（合入 5.1） | 5.8→5.1 | P8 |

### 阶段 B（中等改动，收益高）

| 序号 | 项 | 方案节 | 主要解决问题 |
|------|-----|--------|----------------|
| B1 | `GameState` / Memory 轮次账本 | 5.2 | P1, P2, P4 |
| B2 | 神职私密记忆账本化 ✅ | 5.7 | P4 |
| B3 | 分层 system prompt | 5.5 | P5 |

### 阶段 C（按需）

| 序号 | 项 | 方案节 | 主要解决问题 |
|------|-----|--------|----------------|
| C1 | 每轮 LLM 摘要 | 5.9 | P1, P2（长线局） |
| C2 | 狼队重试策略 | 5.10 | P7 |

---

## 7. 验收与观测

**5.1～5.3、5.5～5.7 自动化验收清单**：[MEMORY_ACCEPTANCE.md](./MEMORY_ACCEPTANCE.md)（`tests/test_memory_acceptance.py`）。

### 7.1 建议增加的指标

- 每次 LLM 调用记录：`phase`、`role`、`input_chars` / 估算 token、`memory_chars` 占比。
- 单局汇总：总调用次数、总 input token、平均每轮 input token。

### 7.2 验收标准（建议）

| 指标 | 目标（相对现状） |
|------|------------------|
| 第 4 轮白天发言单次 input | ↓ 40%+ |
| 投票阶段单次 input | ↓ 50%+ |
| 神职夜晚单次 input | ↓ 30%+ |
| 单局总 input token | ↓ 35%+（阶段 A+B 后） |
| 对局质量 | 无明显退化（人工抽检 3～5 局） |

### 7.3 风险说明

| 优化 | 风险 |
|------|------|
| 裁减远轮发言 | 模型无法引用早期细节发言 |
| 账本化 | 丢失「谁用什么语气说的」 |
| LLM 摘要 | 摘要错误或抹平狼人欺骗链 |
| compact system | 扮演风格变弱 |

---

## 8. 相关代码索引

| 主题 | 路径 |
|------|------|
| 记忆仓与截断 | `memory/memory.py` |
| 上下文拼接 | `memory/context.py` |
| 神职私密账本（5.7） | `memory/god_consolidation.py` |
| 格式化 | `memory/formatter.py` |
| 发布 | `memory/publish.py` |
| Hub | `memory/msg_hub.py` |
| 通用 LLM | `llm/client.py` |
| 狼队频道 | `llm/speech.py` |
| user 去重拼接 | `llm/prompt_format.py` |
| 投票 | `llm/vote.py` |
| 结构化夜晚 | `llm/night.py` |
| 查验历史（结构化） | `game/models.py` → `seer_check_history` |
| 项目结构总览 | `docs/PROJECT_STRUCTURE.md` |

---

## 9. 文档修订

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-18 | 初稿：现状梳理 + 优化方案与问题映射 |
| v0.2 | 2026-05-19 | 5.6 已实现：P6 去重、MEMORY_5.6_PLAN.md |
| v0.3 | 2026-05-19 | 5.7 已实现：P4 神职私密账本、MEMORY_5.7_PLAN.md |
| v0.4 | 2026-05-19 | 5.1–5.7 整体验收见 [MEMORY_ACCEPTANCE.md](./MEMORY_ACCEPTANCE.md) |
| v0.5 | 2026-05-19 | 5.4 v1：生成长度控制见 [MEMORY_5.4_PLAN.md](./MEMORY_5.4_PLAN.md) |
