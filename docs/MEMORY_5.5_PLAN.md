# 5.5 分层 System Prompt — 方案大纲与细节

> **状态**：v1 已实现（`load_system_prompt(role, tier)`、`*_compact.yaml`、`vote`/`night`/`witch`/`hunter` 使用 compact）。  
> **版本**：v1.0（2026-05-19）  
> **关联**：[MEMORY_OPTIMIZATION.md](./MEMORY_OPTIMIZATION.md) 问题 P5；与 5.1～5.4（user/context）正交。

---

## 一、总述

### 1.1 要解决的问题（P5）

每次 Chat Completions 调用结构为：

```text
system: 角色人设（system/{role}.yaml 长文 strategy）
        + advanced_tactics.yaml（全角色通用长文）
user:   局面 + 记忆（5.1/5.2）+ action prompt（投票/刀口/发言指令）
```

现状：**投票、夜晚结构化选目标、女巫 JSON** 等场景只需「身份 + 合法输出 + 遵守局面」，却仍携带完整「扮演 / 心理战 / 伪装层次」散文，**system 段每次全额计费**。

### 1.2 解决方案（一句话）

按 **场景** 选择 system 档位 **`full` / `compact`**：需要长篇扮演用 full；只需选座位号或 JSON 用 compact。

### 1.3 不在 5.5 内

| 包含 | 不包含 |
|------|--------|
| system 消息分档加载 | user 里记忆裁剪（→ 5.1/5.2） |
| 各角色 `*_compact.yaml` 或等价短文案 | 单条发言字数 cap（→ 5.4，可选） |
| 调用方传入 `tier` | 修改 action prompt 正文（仍用现有 `actions/*.yaml`） |

### 1.4 预期收益

- 投票（约 12 次/轮）+ 神职夜（约 4～5 次/轮）+ 猎人开枪等：**system input 降约 60%～80%**（相对 full）。
- 白天发言、狼队频道：**保持 full**，扮演质量不降。

---

## 二、档位定义

### 2.1 `full`（保持现状）

**内容来源**（与现 `load_system_prompt` 一致）：

1. `config/prompts/system/{role}.yaml` → `role_name` + `personality` / `speech_style` + `constraints` + **`strategy` 全文**  
2. 追加 `config/prompts/system/advanced_tactics.yaml`

**使用场景**：

| 模块 | 函数 | 说明 |
|------|------|------|
| `llm/client.py` | `generate_player_response` | 白天讨论发言 |
| `llm/speech.py` | `generate_werewolf_channel_speech` | 狼队频道（full + 频道附加 rules） |
| `llm/wolf_summary.py` | `summarize_wolf_channel` | 可用短 system（见 §2.3 可选） |

### 2.2 `compact`（新建）

**设计原则**：只保留模型做 **结构化决策** 所需信息，删除扮演教程。

**建议每条 compact 包含**（每角色 5～15 行）：

1. 一行身份：`你是预言家，好人阵营。`  
2. **本阶段硬规则**（2～5 条 bullet）：如「只能选一个存活座位号」「不能投自己」。  
3. **输出格式**：与 action/user 中 JSON 约定一致的一句提醒。  
4. **可选**：1 句「依据 user 中的局面与记忆决策，勿编造未发生事件」。

**不包含**：

- `strategy` 长文、`advanced_tactics` 全文  
- 白天伪装、话术模板、心理战章节  

**文件组织（推荐）**：

```text
config/prompts/system/
  werewolf.yaml          # full（现有）
  werewolf_compact.yaml  # compact（新建）
  seer.yaml
  seer_compact.yaml
  …
```

**YAML 结构（与 full 兼容，便于 loader 复用）**：

```yaml
role_name: "预言家"
constraints:
  - "夜间只能查验一名存活玩家，不能查自己。"
  - "依据上下文中的可查验列表选择 target_id。"
output_hint: "返回 JSON：target_id（整数）、reason（不超过30字）。"
# 不写 strategy 字段
```

### 2.3 可选第三档 `minimal`（v1 可不实现）

仅用于 **狼队摘要**、极短分类任务：身份 + 一句任务说明。实现期可 hardcode，不纳入 v1 必做。

---

## 三、场景 → 档位映射表（v1 定稿）

| 场景 | `phase` / 入口 | 文件 | tier |
|------|----------------|------|------|
| 白天发言 | `discuss` → `generate_speech` → `generate_player_response` | `llm/client.py` | **full** |
| 狼队频道 | `generate_werewolf_channel_speech` | `llm/speech.py` | **full** |
| 投票放逐 | `generate_vote` | `llm/vote.py` | **compact** |
| 狼刀 / 预查验 / 守守护 | `generate_night_action` | `llm/night.py` | **compact** |
| 女巫用药 | `generate_witch_night_action` | `llm/witch.py` | **compact** |
| 猎人开枪 | `generate_hunter_shoot` | `llm/hunter.py` | **compact** |
| 投票/夜晚失败兜底自由文本 | `generate_player_response(..., phase=vote/night)` | `llm/client.py` | **compact**（与主路径一致） |
| 狼队战术摘要 | `summarize_wolf_channel` | `llm/wolf_summary.py` | **minimal** 或短 system（可选） |

**注意**：狼人首领 **结构化落刀** 走 `night.py` → **compact**；与白天发言 full 不冲突。

---

## 四、实现设计

### 4.1 API 变更

```python
# config/loader.py
class PromptTier:
    FULL = "full"
    COMPACT = "compact"

def load_system_prompt(self, role: str, tier: str = "full") -> str:
    ...
```

- 缓存键：`(role, tier)`，避免 full/compact 互相覆盖。  
- `tier == "full"`：逻辑与现实现一致。  
- `tier == "compact"`：读 `{role}_compact.yaml`；若缺失则 **fallback** 为 full 并打 warning（或仅 `role_name` + `constraints` 从 full yaml 抽取）。

### 4.2 `_build_compact_prompt`

```python
def _build_compact_prompt(data: dict) -> str:
    parts = [f"你是{data['role_name']}。"]
    constraints = data.get("constraints") or []
    if constraints:
        parts.append("规则：" + "；".join(str(c) for c in constraints))
    hint = (data.get("output_hint") or "").strip()
    if hint:
        parts.append(hint)
    return "\n".join(parts)
```

**不加载** `advanced_tactics`。

### 4.3 调用方改动清单

| 文件 | 改动 |
|------|------|
| `config/loader.py` | `load_system_prompt(role, tier="full")` |
| `llm/vote.py` | `load_system_prompt(role_key, "compact")` |
| `llm/night.py` | 同上 |
| `llm/witch.py` | 同上 |
| `llm/hunter.py` | 同上 |
| `llm/client.py` | 默认 `full`；若 `phase in ("vote", "night")` 且为兜底路径则用 `compact` |
| `llm/speech.py` | 保持 `full` |

### 4.4 与 user/context 的分工（避免重复）

- **compact system**：身份 + 阶段规则 + 输出格式。  
- **user**：`build_*_context` 局面、记忆、候选 id 列表、JSON schema 说明（已在 `vote.py` / `night.py` 追加）。  

不在 compact 里重复候选列表（仍在 user 中）。

---

## 五、各角色 compact 内容要点（撰写参考）

| role_key | compact 须覆盖 |
|----------|----------------|
| `villager` | 好人；投票选一存活他人；JSON |
| `werewolf` | 狼人；刀口/投票目标必须为好人；禁止刀队友；JSON |
| `seer` | 预言家；每夜查验一人；不能查自己；JSON |
| `witch` | 女巫；解药/毒药规则一句；JSON 字段与 `witch_action` schema 一致 |
| `guard` | 守卫；不能守自己、不能连续守同一人；JSON |
| `hunter` | 猎人；开枪选一存活；JSON |

完整条文以 `actions/{phase}.yaml` 为准，compact 只写 **system 侧最硬** 的约束，避免与 user 完全重复。

---

## 六、实施步骤

| 步骤 | 内容 |
|------|------|
| 1 | 新增 6 个 `config/prompts/system/*_compact.yaml` |
| 2 | 扩展 `ConfigLoader.load_system_prompt(role, tier)` |
| 3 | 改 `vote` / `night` / `witch` / `hunter` 使用 `compact` |
| 4 | `client.py` 兜底路径按 phase 选 tier |
| 5 | 单元测试：compact 长度 < full；vote 调用传入 compact |
| 6 | 更新 `MEMORY_OPTIMIZATION.md` §5.5 |

---

## 七、验收用例

1. **长度**：`len(load_system_prompt("werewolf", "compact"))` < `len(..., "full")` / 3`（粗测）。  
2. **功能**：投票/夜晚仍返回合法 `target_id`。  
3. **回归**：白天发言仍用 full，`generate_speech` 行为与改前一致。  
4. **缓存**：同一进程内 `(werewolf, full)` 与 `(werewolf, compact)` 返回不同字符串。

---

## 八、风险与缓解

| 风险 | 缓解 |
|------|------|
| compact 过短导致投票/刀人变呆 | 保留 constraints + user 内完整 context；抽检对局 |
| 与 full 规则不一致 | compact 撰写时对照 full 的 `constraints` 节 |
| 漏改某调用点仍用 full | grep `load_system_prompt` 逐项对照 §三 |

---

## 九、与 5.1～5.4 关系（一图）

```text
单次 LLM 调用 token ≈
  system（5.5 full/compact）
+ user 中 context（5.1 筛选 + 5.2 账本 + 5.3 仓内数据 + 5.4 可选单条 cap）
+ output（max_tokens 配置）
```

---

## 十、修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-19 | 初稿：full/compact 分档与场景映射 |
