"""
LLM 发言类接口：白天公聊、狼队私密频道。

与 client.py 的区别：
  - generate_speech 只是 phase 固定为 discuss 的薄封装
  - generate_werewolf_channel_speech 使用额外 system 约束 + werewolf_channel.yaml
"""
from typing import TYPE_CHECKING

from config.speech_limits import max_tokens_for_phase
from utils.helpers import has_public_day_speech
from llm.client import generate_player_response, loader
from llm.prompt_format import build_user_message
from llm.retry import call_with_transport_retries
from llm.structured import client_from_cfg

if TYPE_CHECKING:
    from game.models import GameState, Player


def werewolf_channel_rules_block(state: "GameState") -> str:
    """5.4：动态频道规则放在 user，保持 system 可缓存。"""
    rules = (
        "【频道须知】当前在狼队私密频道：与狼队友协商刀口，要有独立判断，"
        "禁止全员复读「同意刀X」；跟麦须提出异议、换刀或补充不同战术理由。"
        "不要踩队友，不要伪装成好人。"
    )
    if not has_public_day_speech(state):
        rules += (
            " 本局还没有白天公聊：禁止编造或引用任何玩家已发生的「发言」「带节奏」「投票」；"
            "选刀理由仅限座位、战术或神职猜测。"
        )
    return rules


def generate_speech(
    player_name: str,
    role_key: str,
    context: str,
    round_num: int,
    *,
    player_id: int,
) -> str:
    """白天讨论发言，内部固定 phase='discuss'。"""
    return generate_player_response(
        player_name,
        role_key,
        "discuss",
        context,
        round_num,
        player_id=player_id,
    )


def generate_werewolf_channel_speech(
    player: "Player",
    state: "GameState",
    context: str | None = None,
) -> str:
    """
    狼队私密频道发言。

    返回值应由 roles/werewolf 通过 publish_werewolf 写入 Hub，
    不会直接出现在好人可见的 global 记忆里。
    """
    if context is None:
        context = f"当前第{state.round}轮夜晚，狼队私密讨论。"

    cfg = loader.load_llm_config("werewolf")
    if not cfg.get("api_key"):
        env_name = cfg.get("api_key_env", "API_KEY")
        raise RuntimeError(f"未配置环境变量 {env_name}")

    system_prompt = loader.load_system_prompt("werewolf")
    action_prompt = loader.load_action_prompt("werewolf_channel", "werewolf")
    task_part = loader.render_prompt(
        action_prompt,
        player_id=player.player_id,
        player_name=player.name,
        round=state.round,
    )
    user_message = build_user_message(task_part, context)
    channel_rules = werewolf_channel_rules_block(state)
    user_message = f"{channel_rules}\n\n{user_message}"

    client = client_from_cfg(cfg)
    label = f"{player.name}/werewolf_channel"

    def _create() -> str:
        response = client.chat.completions.create(
            model=cfg["model"],
            temperature=cfg["temperature"],
            max_tokens=max_tokens_for_phase(cfg, "werewolf_channel"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content.strip()

    return call_with_transport_retries(_create, label=label)
