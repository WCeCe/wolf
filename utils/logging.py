"""
对局日志配置。

- 终端：INFO 及以上（便于实时观看）
- game.log：DEBUG 全量（含结构化决策、狼队频道等）
"""
import logging
import sys


def setup_logger(log_file: str = "game.log"):
    logger = logging.getLogger("werewolf")
    logger.setLevel(logging.DEBUG)

    # 避免重复调用 setup_logger 时叠加多个 handler
    if logger.handlers:
        return logger

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
