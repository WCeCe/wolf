"""
5.6 拼 user 消息：任务指令与局面/记忆分块，避免 {context} 在模板内重复嵌入。
"""

SCENE_BLOCK_HEADER = "【局面与记忆】"


def build_user_message(task_part: str, context: str, *, header: str = SCENE_BLOCK_HEADER) -> str:
    """
    将短任务说明与 build_*_context 产出拼接为一条 user 消息。

    context 只出现一次，置于 header 段落下。
    """
    task_part = (task_part or "").strip()
    context = (context or "").strip()
    if not context:
        return task_part
    if not task_part:
        return f"{header}\n{context}"
    return f"{task_part}\n\n{header}\n{context}"
