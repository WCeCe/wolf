# System Prompt 稳定性与狼队频道「首夜 / 公聊」阶段

---

## 1. 你的质疑（复述与结论）

**你的推理：**

1. 第 1 轮夜晚：尚无白天公聊 → 狼队应用「首夜 / 无公聊」约束。  
2. 第 2 轮夜晚：第 1 轮已完整白天讨论 → 应切换到「已有公聊」约束。  
3. 若第 2 轮狼队频道仍说「**首轮**淘汰某某合理」，则怀疑 **system（或整体 prompt）仍停在首夜模式**。

**结论（分两层）：**

| 层次 | 对你这局（19:48 旧代码） | 对当前仓库 |
|------|-------------------------|------------|
| **R1 夜 vs R2 夜 system 是否不同** | **是。** 旧版把「无公聊」规则 **拼在 system 末尾**，两夜 system 字符串不同 → Prompt Cache 对 system 不友好。 | **已修：** system 仅 `werewolf.yaml` + tactics，**R1/R2 相同**；阶段差异只在 **user**（`【频道须知】` + 局面块）。 |
| **R2 夜说「首轮」是否证明 R2 仍用 R1 的 system** | **不能单独证明。** R2 夜旧版 system 已去掉「还没有白天公聊」段，理论上比 R1 **更短**，不是「仍卡在 R1 system」。日志里「首轮」是 **模型发言**，不是 system 打印。 | 更可能是：① 静态人设 yaml 里仍写有「**如首夜**」② 模型把「首轮出局风险」当口语 ③ **少数狼人 memory 未 sync 全**时 `has_public_day_speech` 曾可能不稳（已用 `day_discussion_occurred` 加固）。 |

**直接回答：你对「首夜 / 次夜 system 不一致」的担心，在旧代码里成立；第 2 轮那句「首轮」更像是模型没跟上局面，而不是日志里还能看见 system 切回了首夜。**

---

## 2. 旧版 vs 现行：狼队频道 prompt 结构

### 2.1 旧版（你跑 19:48 局时）

```text
system = load_system_prompt("werewolf") + channel_rules(动态)
         ↑ 固定                          ↑ R1 夜含「无公聊」；R2 夜去掉 → system 变短
user   = channel_rules 已在 system + task + 【局面与记忆】
```

→ **R1 夜 ≠ R2 夜 system**（你的怀疑正确）。

### 2.2 现行（5.4 之后）

```text
system = load_system_prompt("werewolf")     # 整局不变，可 Cache
user   = 【频道须知】(动态，仅 user)
       + task（含 round）
       + 【局面与记忆】（含「当前第 N 轮」；有公聊时含「勿称首夜/首轮」）
```

→ **R1 夜 = R2 夜 system**；差异只在 user。

---

## 3. 第 2 轮为何还会说出「首轮」？

即使 user 已写「已进行过公聊」，模型仍可能说「首轮」，常见原因：

1. **system 人设长文里永久含有**「尚无白天公聊时（如**首夜**）」——不随轮次删除，模型被锚定。  
2. **「首轮出局风险」** 被模型当作「早期不容易被投出去」的口语，不是严格指 R1。  
3. **旧 `has_public_day_speech`** 扫 `memories`：若某狼 R1 发言顺序靠前、之后未 sync，理论上存在极端误判（已通过 `day_discussion_occurred` 修复）。

**现行对策：**

- `GameState.day_discussion_occurred`：白天讨论结束置 `True`，`has_public_day_speech` **优先读此标志**。  
- 已有公聊时，狼队频道若含「首夜 / 首轮 / 尚未公聊」等 → **重试一次**（`references_stale_first_night_wording`）。

---

## 4. 如何自证下一局

1. 用**当前代码**跑局。  
2. 第 2 轮狼队若仍说「首轮」，日志应出现：`狼队频道使用了首夜/首轮等过时表述…重试一次`。  
3. 可选 DEBUG：对 `load_system_prompt("werewolf")` 打 `hash`，R1/R2 夜应相同。

---

## 5. Prompt Cache 备忘

- **system**：同角色狼队频道整局应 Hit（现行）。  
- **user**：`【频道须知】` 在「第一次白天结束后」变一次；每轮局面仍变 → user 仍大量 Miss。

---

## 文档修订

| 版本 | 说明 |
|------|------|
| v0.1 | 初版（偏「发言不是 system」） |
| v0.2 | 按用户澄清重写：首夜/次夜 system 差异 + R2「首轮」含义 |
