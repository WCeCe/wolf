# 5.6 去除 Context 重复拼接 — 方案大纲与细节

> **状态**：v1 已实现（`llm/prompt_format.py`、`build_user_message`、action 模板去 `{context}`、各 `llm/*` 统一拼接）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 **P6**；与 5.1～5.5 正交（5.1/5.2 决定 context **内容**，5.6 决定 context **只出现一次**）。

---

## 一、总述

### 1.1 要解决的问题（P6）

`memory/context.py` 的 `build_*_context` 已输出完整「局面 + 记忆」文本，但旧版 user 消息在多处 **再次嵌入同一段**：

| 场景 | 重复方式 |
|------|----------|
| 白天发言 / 投票 | `discuss.yaml` / `vote.yaml` 的 `场上信息：{context}` |
| 狼队频道 | `render` 后末尾再贴 `【局面信息】\n{context}`（与 `build_werewolf_channel_context` 同文） |
| 夜晚结构化 | `_night_action_user_message` 前缀 `你是 X 号` + context 内已有身份行 |
| 猎人开枪 | task 含轮次/座位 + `【局面信息】\n{context}` 二次粘贴 |

同一段 token 在 **单次 API 调用** 里计费两次，约浪费 user 侧 **10%～25%**（视局数与记忆长度而定）。

### 1.2 解决方案（一句话）

**任务指令（短）** 与 **局面/记忆（`build_*_context`）** 分块：模板不再含 `{context}`；代码用统一 helper **只追加一次**。

### 1.3 不在 5.6 内

| 包含 | 不包含 |
|------|--------|
| user 消息结构去重 | 记忆内容裁剪（→ 5.1/5.2/5.3） |
| action 模板删 `{context}` | system prompt 分档（→ 5.5） |
| 统一块标题 `【局面与记忆】` | 狼队重试时不重复 ctx（→ 5.10） |

---

## 二、目标 user 消息结构

```text
{instruction + role task}          ← 来自 actions/*.yaml，无局面全文

【局面与记忆】
{build_*_context 的完整输出}       ← 只出现一次

【结构化输出】…                    ← vote / night / hunter 等附加（若有）
【女巫行动约束】…                  ← witch 专有（若有）
```

**原则**：

- 轮次、座位、身份、存活列表、记忆 `<history>` **只在 context 块**出现。
- task 段只保留「阶段目标 + 自称规则 + 角色立场一句」。
- 结构化 JSON 说明放在 context **之后**，避免夹在重复正文中间。

---

## 三、实现清单

### 3.1 新增模块

| 文件 | 说明 |
|------|------|
| `llm/prompt_format.py` | `SCENE_BLOCK_HEADER = "【局面与记忆】"`；`build_user_message(task_part, context)` |

### 3.2 模板变更

| 文件 | 变更 |
|------|------|
| `config/prompts/actions/discuss.yaml` | 删除 `{context}`、删除 task 内「当前第{round}轮」；instruction 指向下方块 |
| `config/prompts/actions/vote.yaml` | 删除 `{context}`、座位/轮次重复行 |
| `config/prompts/actions/hunter_shoot.yaml` | 删除 `{context}` 与 task 内轮次 |
| `config/prompts/actions/night.yaml` | 本无 `{context}`，保持不变 |

### 3.3 调用方

| 模块 | 变更 |
|------|------|
| `llm/client.py` | `render` 不传 `context` → `build_user_message` |
| `llm/speech.py` | 狼队频道：单次 `build_user_message`（标题与全项目统一） |
| `llm/vote.py` | `_vote_user_message` |
| `llm/night.py` | 去掉多余 `你是 X 号` 前缀 |
| `llm/hunter.py` | 去掉 `【局面信息】` 二次粘贴 |
| `llm/witch.py` | `build_user_message` + `【女巫行动约束】`（原「私密信息」改名，避免与 context 内「私密」混淆） |

---

## 四、验收

### 4.1 自动

- `tests/test_prompt_format.py`：`{context}` 不在 action 模板；`build_user_message` 后 context 子串只出现 1 次。

### 4.2 人工抽检（建议）

- 跑 1 局：日志或 debug 打印单次 `user` 长度，对比 5.6 前同轮次（应下降且语义完整）。
- 白天发言仍以「我是 N 号」开头；投票/夜行 JSON 仍能解析 `target_id`。

---

## 五、风险与回滚

| 风险 | 缓解 |
|------|------|
| 模型找不到「场上信息」 | instruction 明确写「依据下方【局面与记忆】」 |
| 狼队频道习惯旧标题 `【局面信息】` | 统一为 `【局面与记忆】`，语义不变 |
| 某 yaml 仍留 `{context}` 未替换 | 单测 grep + code review |

回滚：恢复 yaml 内 `{context}` 并去掉 `build_user_message` 调用即可（与 5.1+ 记忆策略独立）。

---

## 六、相关索引

| 主题 | 路径 |
|------|------|
| 拼接 helper | `llm/prompt_format.py` |
| 局面+记忆正文 | `memory/context.py` |
| 讨论 / 投票模板 | `config/prompts/actions/discuss.yaml`, `vote.yaml` |
| 总纲 §5.6 | [MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) |
