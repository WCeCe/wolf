"""
项目入口（12 人标准局：4 狼 + 4 神 + 4 村民）。

在项目根目录执行: python main.py
需先配置 config/llm_config.yaml 中指定的 API Key 环境变量。
详细结构见 docs/PROJECT_STRUCTURE.md
"""
from game import run_game

if __name__ == "__main__":
    run_game()
