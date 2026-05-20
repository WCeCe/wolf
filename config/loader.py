"""
配置与 Prompt 加载器。

职责：
  - load_llm_config：合并 profiles + 角色覆盖，从环境变量读 api_key
  - load_system_prompt：角色人设（system/{role}.yaml）+ 通用技巧（system/advanced_tactics.yaml）
  - load_action_prompt：阶段行动指令（config/prompts/actions/{phase}.yaml）
  - render_prompt：简单 {变量} 替换
"""
import logging
import os
from pathlib import Path

import yaml
from typing import Dict, Any, Tuple

_CONFIG_DIR = Path(__file__).resolve().parent

logger = logging.getLogger("werewolf")

# 5.5 分层 system prompt
PROMPT_TIER_FULL = "full"
PROMPT_TIER_COMPACT = "compact"


class ConfigLoader:
    def __init__(self, config_dir: str | None = None):
        self.config_dir = config_dir or str(_CONFIG_DIR)
        self._cache: Dict[Tuple[str, str], str] = {}  # (role, tier) -> system prompt
        self._advanced_tactics: str | None = None  # 全角色通用技巧，懒加载

    def load_llm_config(self, role: str = None) -> Dict[str, Any]:
        """
        加载 LLM 连接配置。

        llm_config.yaml 结构：
          profiles: 完整模型配置（ds / doubao / kimi …）
          roles: 各游戏角色选用哪个 profile，可覆盖 temperature 等
        """
        config_path = Path(self.config_dir) / "llm_config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        profiles = config.get("profiles", {})
        default_profile = config.get("default_profile", "ds")
        if default_profile not in profiles:
            raise ValueError(f"default_profile '{default_profile}' not found in profiles")

        base = dict(profiles[default_profile])
        if role and role in config.get("roles", {}):
            role_cfg = dict(config["roles"][role])
            profile_name = role_cfg.pop("profile", default_profile)
            if profile_name not in profiles:
                raise ValueError(f"profile '{profile_name}' for role '{role}' not found in profiles")
            base = dict(profiles[profile_name])
            base.update(role_cfg)

        env_name = base.get("api_key_env", "")
        raw = os.getenv(env_name) if env_name else None
        base["api_key"] = raw.strip() if raw else None
        return base

    def _load_advanced_tactics(self) -> str:
        """加载 config/prompts/system/advanced_tactics.yaml（全角色共用）。"""
        if self._advanced_tactics is not None:
            return self._advanced_tactics
        filepath = os.path.join(
            self.config_dir, "prompts", "system", "advanced_tactics.yaml"
        )
        if not os.path.isfile(filepath):
            self._advanced_tactics = ""
            return ""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._advanced_tactics = (data.get("advanced_tactics") or "").strip()
        return self._advanced_tactics

    @staticmethod
    def _build_system_prompt(data: Dict[str, Any]) -> str:
        """
        将 system/{role}.yaml 拼成 system message。

        字段：
          - role_name: 必填
          - personality / speech_style: 可选，拼在身份介绍后
          - constraints: 可选，硬性规则列表
          - strategy: 可选，长文策略
        """
        intro_parts = [f"你是{data['role_name']}"]
        for key in ("personality", "speech_style"):
            text = (data.get(key) or "").strip()
            if text:
                intro_parts.append(text)
        parts = ["。".join(intro_parts) + "。"]

        constraints = data.get("constraints") or []
        if constraints:
            parts.append("请注意：" + " ".join(str(c) for c in constraints))

        strategy = (data.get("strategy") or "").strip()
        if strategy:
            parts.append(strategy)

        return "\n\n".join(parts)

    @staticmethod
    def _build_compact_prompt(data: Dict[str, Any]) -> str:
        """5.5 compact：身份 + 硬规则 + 输出提示，不含 strategy / advanced_tactics。"""
        parts = [f"你是{data['role_name']}。"]
        constraints = data.get("constraints") or []
        if constraints:
            parts.append("规则：" + "；".join(str(c) for c in constraints))
        hint = (data.get("output_hint") or "").strip()
        if hint:
            parts.append(hint)
        return "\n".join(parts)

    def load_system_prompt(self, role: str, tier: str = PROMPT_TIER_FULL) -> str:
        """
        加载并缓存角色 system prompt。

        tier:
          - full: system/{role}.yaml + advanced_tactics（白天发言、狼队频道）
          - compact: system/{role}_compact.yaml（投票、夜晚结构化）
        """
        if tier not in (PROMPT_TIER_FULL, PROMPT_TIER_COMPACT):
            tier = PROMPT_TIER_FULL

        cache_key = (role, tier)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if tier == PROMPT_TIER_COMPACT:
            filepath = os.path.join(
                self.config_dir, "prompts", "system", f"{role}_compact.yaml"
            )
            if not os.path.isfile(filepath):
                logger.warning(
                    "未找到 %s，compact 回退为 full system prompt", filepath
                )
                return self.load_system_prompt(role, PROMPT_TIER_FULL)
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            prompt = self._build_compact_prompt(data)
        else:
            filepath = os.path.join(self.config_dir, "prompts", "system", f"{role}.yaml")
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            prompt = self._build_system_prompt(data)
            tactics = self._load_advanced_tactics()
            if tactics:
                prompt = f"{prompt}\n\n{tactics}"

        self._cache[cache_key] = prompt
        return prompt

    def load_action_prompt(self, phase: str, role: str = None) -> str:
        """加载 actions/{phase}.yaml；若含该 role 字段则追加角色专属 task。"""
        filepath = os.path.join(self.config_dir, "prompts", "actions", f"{phase}.yaml")
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        instruction = (data.get("instruction") or "").strip()
        if phase == "discuss":
            from config.speech_limits import discuss_length_instruction

            instruction = f"{instruction} {discuss_length_instruction()}".strip()
        elif phase == "last_words":
            from config.speech_limits import discuss_length_instruction

            instruction = (
                f"{instruction} {discuss_length_instruction()}（遗言同样适用篇幅要求）"
            ).strip()

        if role and role in data:
            return f"{instruction} {data[role]['task']}"
        return instruction

    def render_prompt(self, template: str, **kwargs) -> str:
        """替换模板中的 {player_name}、{round}、{player_id} 等占位符（context 由 build_user_message 拼接，勿嵌入模板）。"""
        for key, value in kwargs.items():
            template = template.replace("{" + key + "}", str(value))
        return template
