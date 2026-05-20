# Agent-Werewolf 全项目优化审查（2026-05-19）

> 基于代码通读、`GAME_BUGS.md` 台账、记忆 5.x 文档与测试结构的综合结论。  
> 本次已在代码中落地部分 P1/P2 修复；其余为建议路线图。

---

## 1. 项目健康度概览

| 维度 | 评价 | 说明 |
|------|------|------|
| 架构分层 | 优 | `game`（阶段机）→ `roles`（身份流程）→ `llm` / `memory` 清晰，依赖方向正确 |
| 规则可测性 | 良 | `ledger`、`night_resolution`、遗言等有单测；缺「整局集成」mock 测试 |
| 记忆系统 | 良 | 5.1–5.7 已落地，文档与 `test_memory_acceptance` 对齐 |
| LLM 可控性 | 中 | 结构化夜晚行动较好；白天发言长度仍依赖模型自觉（GB-007） |
| 运维/工程 | 中 | 无 `requirements.txt` / `pyproject.toml`；测试用 `unittest` 而非 pytest |

---

## 2. 已在本轮实现的修复

| ID | 改动 | 文件 |
|----|------|------|
| GB-004 | 玩家出局时 `on_player_eliminated` → `MsgHub.remove_werewolf`；狼队日志改为「存活狼可见」 | `memory/publish.py`、`msg_hub.py`、`night_resolution.py`、`voting.py`、`hunter.py` |
| GB-003 | 猎人公布与死讯分离（白天/投票前增加 system 分隔）；公开文案注明不公布身份 | `game/phases/day.py`、`voting.py`、`roles/hunter.py` |
| GB-007 | 发言超 250 字打 `warning`，不截断 | `config/speech_limits.py`、`roles/base.py` |
| GB-008 | `discuss.yaml` 禁止空泛套话复读 | `config/prompts/actions/discuss.yaml` |

新增测试：`tests/test_player_elimination.py`。

---

## 3. 规则与体验：待办与建议

### 3.1 仍建议人工验收（见 `GAME_BUGS.md` 清单）

- 猎人夜间死亡：全场 memory 含「猎人带走 Y 号」
- 死狼不出现在狼队日志「存活狼可见」
- 白天单条发言多数 ≤200 字（目前仅 warning）

### 3.2 可选产品向改动

| 项 | 建议 | 风险 |
|----|------|------|
| GB-005 女巫毒药 | 后期轮次在 `witch` prompt 强调「毒药仍可用」 | 可能破坏平衡 |
| GB-007 硬截断 | 按句保险丝截到 ~180 字（会改玩家原话） | 体验 vs token |
| 投票平票 | 部分板子支持 PK 或警长票；当前「平票无人出局」已文档化 | 改规则需全盘回归 |
| 多狼分刀 | `WerewolfHandler` 目前首领落刀；扩展需改 `night_actions` 结构 | 工作量大 |

---

## 4. 架构与代码质量建议

### 4.1 工程化（优先级：高）

1. **添加 `pyproject.toml` 或 `requirements.txt`**  
   固定 `openai`、`pyyaml` 版本；CI 可 `pip install -e .[dev]` + `unittest discover`。

2. **README.md**  
   根目录缺失；可从 `docs/PROJECT_STRUCTURE.md` §9 摘一版快速开始。

3. **`.gitignore` 确认包含 `game.log`、`.venv`**  
   避免误提交对局日志与虚拟环境。

### 4.2 消除重复与单点（优先级：中）

| 问题 | 建议 |
|------|------|
| 出局收束分散在 3 处 | 已收敛为 `on_player_eliminated`；后续若加「死亡动画/统计」可在此扩展 |
| `GameState.public_log` vs `publish_global` | 文档已说明双轨；长期可考虑只保留 publish，log 由 DEBUG 导出 |
| 猎人开枪：投票路径与夜晚路径 | 已统一 `HunterHandler`；投票阶段可复用与 day 相同的 header 文案常量 |

### 4.3 记忆与 Token（优先级：中，见 MEMORY_* 文档）

- **5.9 远轮公聊 LLM 摘要**：公聊 K 轮外仍膨胀时，用零 LLM 规则摘要或轻量模型压缩。
- **Prompt Cache**：`STABLE_SYSTEM.md` 已说明；确保 vote/night 走 compact tier（已实现）。
- **狼队白天**：已用 `wolf_night_summary`；可监控摘要失败率（`wolf_summary.py` fallback 日志）。

### 4.4 LLM 可靠性（优先级：中）

| 点 | 现状 | 建议 |
|----|------|------|
| 重试 | `llm/retry.py` 传输层重试 | 对 429/5xx 区分退避；结构化失败已有兜底 |
| 结构化 | json_schema → json_object 回退 | 记录每角色失败率，按需换更听话模型 |
| 发言质检 | 狼队频道有「引用不存在白天信息」重试 | 白天 discuss 可对「未自称座位号」做同样一次重试 |

### 4.5 测试缺口（优先级：中）

| 建议新增 | 目的 |
|----------|------|
| `test_day_phase_hunter_order.py` | 死讯 → header → 开枪公布顺序 |
| `test_voting_hunter_vote.py` | 放逐猎人 → 遗言 → 开枪 |
| Mock LLM 的 1 局 smoke | 不耗 API 验证三阶段串行 |
| `test_guard_consecutive.py` | 连守非法目标兜底 |

运行现有测试：

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
```

---

## 5. 矛盾与文档不一致（已核对）

| 点 | 结论 |
|----|------|
| `msg_hub` TODO「发言无座位号」 | **已解决**：`memory/formatter.py` 已格式化为 `3号:`；可删 TODO（本轮已删） |
| GB-003「无广播」 | 代码一直有 `publish_global`；问题是顺序/淹没/日志含身份 → 已加强分隔与文案 |
| `get_players_by_role` 含死者？ | **否**，仅存活；GB-004 主要是 `werewolf_ids` 集合未收缩 |
| 夜晚顺序 vs 文档 | `NIGHT_CAMP_ORDER` 守卫→狼→预→女，与 `PROJECT_STRUCTURE.md` 一致 |

---

## 6. 创新方向（自由探索）

1. **观战/复盘模式**：用 `round_ledger` + `discussion_log` 生成 Markdown 战报，零 LLM。
2. **人类玩家接入**：某座位改为 stdin/API，其余仍为 Agent。
3. **Elo / 角色胜率**：结构化记录每局胜负与身份，评估 prompt 迭代效果。
4. **反共谋检测**：狼队频道与公聊 embedding 相似度过高时 warning（防模型「频道说人话」）。
5. **配置化板子**：`setup.py` 身份池改为 YAML（10 人局、狼王局等）。

---

## 7. 建议执行顺序（路线图）

```
阶段 A（已完成）: GB-004、GB-003 体验、GB-007 warning、GB-008 prompt
阶段 B（1–2 天）: requirements + README + unittest CI
阶段 C（按需）   : 发言硬截断 / 女巫毒药 prompt / 5.9 远轮摘要
阶段 D（长期）   : 多狼分刀、人类座位、战报生成
```

---

## 8. 文档修订

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-19 | 首轮全项目审查 + 部分代码落地 |
