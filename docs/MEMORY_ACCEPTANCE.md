# 记忆优化 5.1～5.3、5.5～5.7 验收清单

> 自动化：`python -m unittest discover -s tests -v`（含 `test_memory_acceptance.py`）。  
> 5.8（狼队白天解耦）未单独列项：已由 5.1 覆盖。

---

## 5.1 阶段感知出库

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 1 | 讨论公聊窗口 | 最近 2 轮 `speech` | `SPEECH_ROUNDS_DISCUSS=2`；`test_villager_vote` / acceptance |
| 2 | 投票公聊窗口 | 最近 1 轮 | `SPEECH_ROUNDS_VOTE=1` |
| 3 | 狼人白天 | 仅 `wolf_night_summary`，无 `werewolf_memory` 全文 | `test_werewolf_discuss_*` |
| 4 | 狼队频道 | 仅当夜频道 + system 最近 10 条 | `test_werewolf_channel_tonight_only` |
| 5 | 神职夜晚 | 无 speech、无私密原文 | `test_god_night_*` |
| 6 | 狼队 LLM 摘要 | 落刀后 `summarize_wolf_channel` → `wolf_night_summary` | `roles/werewolf.py` |

## 5.2 局面账本

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 7 | 远轮要点 | `round ≤ current−K` 进【局面账本】 | `test_ledger_*` |
| 8 | 与远轮 system 去重 | 有 K 时裁掉更老 `system_info` | `test_selection_includes_ledger_excludes_old_system` |

## 5.4 白天公聊生成长度（prompt + max_tokens）

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 19 | discuss 篇幅指引 | instruction 含 120～180 与「完整」 | `test_speech_limits` |
| 20 | discuss API 上限 | `max_tokens_for_phase(..., "discuss")` 默认 180 | `test_speech_limits` |
| 21 | 无写时截断 | `publish` 不裁剪 speech | 代码审查 / `publish.py` 仅 warning |
| 22 | 狼队 system 静态 | 动态规则在 `werewolf_channel_rules_block` → user | `test_speech_limits` |

## 5.3 分类型截断

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 9 | public 分桶 | system / speech 分别 cap 80 / 36 | `test_memory_truncate` |
| 10 | 狼队频道仓 | 狼人 `werewolf` cap 64 | `test_werewolf_channel_cap_64` |
| 11 | 神职 private 仓 | 预言家 40、女巫 30、守卫 20 | `test_*_private_cap_*` |

## 5.5 分层 system prompt

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 12 | compact 更短 | 无 strategy / advanced_tactics | `test_prompt_tier` |
| 13 | 使用场景 | vote / night / witch / hunter → compact；discuss / 狼队频道 → full | `llm/client.py`、`vote.py`、`night.py` 等 |

## 5.6 user 去重

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 14 | 模板无 `{context}` | discuss / vote / hunter_shoot | `test_prompt_format` |
| 15 | 单块局面 | `build_user_message` 只拼一次【局面与记忆】 | `test_build_user_message_*` |

## 5.7 神职私密账本

| # | 验收项 | 预期 | 验证 |
|---|--------|------|------|
| 16 | 白天神职 | `build_player_context` 含【*私密账本】，无【私密信息】叙述 | `test_god_consolidation` / acceptance |
| 17 | 女巫用药史 | `witch_potion_log` 每夜追加 | `test_append_witch_potion_log` |
| 18 | 神职夜晚 | selection 仍 `private_messages=[]` | `test_god_night_*` |

---

## 人工抽检（建议每版发版前 1 局）

- [ ] 第 3 轮白天：狼人 context 含【狼队战术摘要】且无大段频道原文
- [ ] 预言家白天能引用历史查验，且无重复「你查验了…」长句
- [ ] 投票/夜行 JSON 仍能解析，发言仍以「我是 N 号」开头

---

## 已知非目标（勿在本轮验收判失败）

- 5.4 写时硬截断、二次 LLM 压摘要
- 5.8 单独工程（已合入 5.1）
- 5.9 远轮 LLM 公聊摘要
- 5.10 狼队重试减载
