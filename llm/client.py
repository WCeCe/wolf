"""
LLM 通用客户端：自由文本对话。

所有「返回一段话」的场景（白天发言、兜底夜晚行动）最终都走 generate_player_response。
流程：加载角色配置 → 拼 system + action prompt → 调用 Chat Completions。
"""
from config.loader import PROMPT_TIER_COMPACT, PROMPT_TIER_FULL, ConfigLoader
from config.speech_limits import max_tokens_for_phase
from llm.prompt_format import build_user_message
from llm.retry import call_with_transport_retries
from llm.structured import client_from_cfg

loader = ConfigLoader()


def generate_player_response(
    player_name: str,
    role_key: str,
    phase: str,
    context: str,
    round_num: int,
    *,
    player_id: int | None = None,
) -> str:
    """
    调用 LLM 生成某玩家在当前阶段的自由文本回复。

    Args:
        player_name: 显示名
        role_key: werewolf / seer / villager / witch，对应 config 与 prompt
        phase: discuss / night 等，对应 config/prompts/actions/{phase}.yaml
        context: 由 memory.context 拼好的局面与记忆
        round_num: 当前轮次，填入 prompt 模板
        player_id: 座位号，填入 prompt 模板（白天发言、投票等）
    """
    cfg = loader.load_llm_config(role_key)
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    tier = PROMPT_TIER_COMPACT if phase in ("vote", "night") else PROMPT_TIER_FULL
    system_prompt = loader.load_system_prompt(role_key, tier)
    action_prompt = loader.load_action_prompt(phase, role_key)
    render_kwargs: dict = {
        "player_name": player_name,
        "round": round_num,
    }
    if player_id is not None:
        render_kwargs["player_id"] = player_id
    task_part = loader.render_prompt(action_prompt, **render_kwargs)
    user_message = build_user_message(task_part, context)

    client = client_from_cfg(cfg)
    label = f"{player_name}/{phase}"

    def _create() -> str:
        response = client.chat.completions.create(
            model=cfg["model"],
            temperature=cfg["temperature"],
            max_tokens=max_tokens_for_phase(cfg, phase),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content.strip()

    return call_with_transport_retries(_create, label=label)
