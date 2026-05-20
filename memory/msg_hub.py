"""
MsgHub（消息中心）：广播与拉取。

设计要点：每个玩家有独立队列（fan-out），
若全服共用一个 Queue，第一个 fetch 的玩家会把别人的消息也取走。

时序：
  事件后 broadcast → 玩家行动前 fetch_all（清空该玩家队列）→ update_from_hub
"""
from queue import Queue
from typing import Dict, List, Set

from .message import Message, Channel


class MsgHub:
    def __init__(self, player_ids: List[int], werewolf_ids: List[int] | None = None):
        self.player_ids: List[int] = list(player_ids)
        self.werewolf_ids: Set[int] = set(werewolf_ids or [])

        # 三个频道 × 按玩家分队列（未读信箱）
        self._global: Dict[int, Queue] = {pid: Queue() for pid in self.player_ids}
        self._werewolf: Dict[int, Queue] = {pid: Queue() for pid in self.werewolf_ids}
        self._private: Dict[int, Queue] = {pid: Queue() for pid in self.player_ids}

    def broadcast(self, msg: Message) -> None:
        """根据 msg.channel 把消息复制进对应玩家的队列。"""
        if msg.channel == Channel.GLOBAL:
            targets = msg.visible_to if msg.visible_to else self.player_ids
            for pid in targets:
                if pid in self._global:
                    self._global[pid].put(msg)

        elif msg.channel == Channel.WEREWOLF:
            targets = msg.visible_to if msg.visible_to else list(self.werewolf_ids)
            for pid in targets:
                if pid in self._werewolf:
                    self._werewolf[pid].put(msg)

        elif msg.channel == Channel.PRIVATE:
            if not msg.visible_to:
                raise ValueError("Private message must specify visible_to.")
            for pid in msg.visible_to:
                if pid in self._private:
                    self._private[pid].put(msg)

    def remove_werewolf(self, player_id: int) -> None:
        """出局狼人从 werewolf_ids 移除，不再接收狼队频道广播（GB-004）。"""
        self.werewolf_ids.discard(player_id)

    def fetch_all(self, player_id: int, is_werewolf: bool = False) -> Dict[str, list]:
        """
        拉取该玩家自上次 fetch 以来的新消息，并清空其个人队列。

        返回键名与 PlayerMemory.update_from_hub 约定一致：
          global / private / werewolf
        非狼人切勿传 is_werewolf=True。
        """
        result: Dict[str, list] = {"global": [], "werewolf": [], "private": []}

        if player_id in self._global:
            q = self._global[player_id]
            while not q.empty():
                result["global"].append(q.get_nowait())

        if is_werewolf and player_id in self._werewolf:
            q = self._werewolf[player_id]
            while not q.empty():
                result["werewolf"].append(q.get_nowait())

        if player_id in self._private:
            q = self._private[player_id]
            while not q.empty():
                result["private"].append(q.get_nowait())

        return result
