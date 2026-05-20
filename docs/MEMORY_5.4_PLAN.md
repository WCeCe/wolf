# 5.4 白天公聊生成长度控制 — 方案大纲与细节

> **状态**：v1 已实现（prompt 字数约束 + `discuss_max_tokens`；**无** `publish_*` 写时截断）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 **P1**；与 5.1 出库窗口正交（5.4 压 **单条** 体积，5.1 压 **条数**）。

---

## 一、总述

### 1.1 要解决的问题（P1 子集）

白天 `publish_global(..., data_type="speech")` 写入的记忆条可能很长（旧版 `max_tokens: 500`、discuss 无字数约束）。单条越大，之后每次 `get_context_for_llm` 拼进 **user** 的体积越大，且 **难以 Prompt Cache 命中**。

### 1.2 解决方案（C 方案：生成时控长，不砍入库）

| 层级 | 做法 |
|------|------|
| **主路径** | `discuss.yaml` + `discuss_length_instruction()`：要求 **120～180 字、一段完整公聊** |
| **硬上限** | API `max_tokens` 使用 `discuss_max_tokens`（默认 180），与字数目标对齐 |
| **人设/风格** | 仍用 **full system** + 各角色 task 语气提示；**不**为省 token 改 compact |
| **明确不做** | `publish_global` / `publish_werewolf` **写时截断**（避免断句毁体验） |

模型偶发超长：v1 **不裁剪**；若实测违规率高，再评估「按句号保险丝」或 5.9 轮次摘要，不默认硬砍。

### 1.3 附带：狼队频道 system 静态化（利于 Prompt Cache）

`generate_werewolf_channel_speech` 不再把「首夜/是否已有公聊」等 **动态句** 拼进 `system`；改为 **user 前缀 `【频道须知】`**。  
`system` 仅 `load_system_prompt("werewolf")` full 人设，字节级稳定，重复调用更易 Cache Hit。

频道长度仍由 `werewolf_channel.yaml` 的「50 字以内」+ `werewolf_channel_max_tokens`（默认 100）约束。

### 1.4 不在 5.4 内

| 包含 | 不包含 |
|------|--------|
| 白天 discuss 生成长度 | 投票阶段篇幅（可后续单独加） |
| discuss / 狼队频道 `max_tokens` | 5.9 每轮 LLM 公聊摘要 |
| 狼队频道 system 静态化 | publish 后截断、二次 LLM 压摘要 |

---

## 二、常量与配置

| 符号 | 默认值 | 说明 |
|------|--------|------|
| `DISCUSS_CHAR_MIN` / `MAX` | 120 / 180 | 写入 prompt 的中文篇幅指引 |
| `DISCUSS_MAX_TOKENS_DEFAULT` | 180 | discuss 阶段 API 上限 |
| `WEREWOLF_CHANNEL_MAX_TOKENS_DEFAULT` | 100 | 狼队频道（约 50 字） |

`config/llm_config.yaml` 可在 profile 或 `roles.*` 覆盖：

```yaml
discuss_max_tokens: 180
werewolf_channel_max_tokens: 100
```

---

## 三、实现清单

| 文件 | 变更 |
|------|------|
| `config/speech_limits.py` | 常量、`discuss_length_instruction()`、`max_tokens_for_phase()` |
| `config/loader.py` | `load_action_prompt("discuss")` 追加篇幅 instruction |
| `config/prompts/actions/discuss.yaml` | 各角色 task 补充语气/结构提示 |
| `config/llm_config.yaml` | `discuss_max_tokens` / `werewolf_channel_max_tokens` |
| `llm/client.py` | discuss 使用 `max_tokens_for_phase` |
| `llm/speech.py` | 频道规则进 user；`max_tokens_for_phase("werewolf_channel")` |
| `tests/test_speech_limits.py` | 契约测试 |

---

## 四、验收

| # | 项 | 预期 |
|---|-----|------|
| 1 | discuss instruction | 含 `120`～`180` 与「完整」 |
| 2 | discuss API | `max_tokens` ≤ `discuss_max_tokens`（默认 180） |
| 3 | 无 publish 截断 | `publish.py` 无新增 cap 逻辑 |
| 4 | 狼队 system | 不含「本局还没有白天公聊」等动态串 |
| 5 | 狼队 user | 含 `【频道须知】`（首夜时含禁止编造公聊） |

人工：跑 1 局，抽查白天发言是否多为一段、约一两百字；`game.log` 中单条 speech 长度分布。

---

## 五、风险

| 风险 | 缓解 |
|------|------|
| 模型仍超长 | 调低 `discuss_max_tokens`；加强 task |
| 过短、信息不足 | 调高 `DISCUSS_CHAR_MIN` 或 max_tokens |
| 风格变弱 | 保持 full system；角色 task 保留语气词 |

---

## 六、文档修订

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-19 | 生成时控长 v1；放弃写时截断 |
