"""
任务队列：多链接自动排队，限制并发与单用户频率。
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from loguru import logger

from config.config import cfg


@dataclass
class GalleryTask:
    gid: str
    token: str
    user_id: int
    chat_id: int
    message_id: int  # 用于后续编辑状态
    source: str = "manual"  # "manual" | "crawl"


_queue: asyncio.Queue = None
_max_concurrent = 2
_user_times: dict = None  # user_id -> deque of timestamps
_per_minute = 2
_lock = asyncio.Lock()


def init_queue():
    global _queue, _max_concurrent, _user_times, _per_minute
    _queue = asyncio.Queue()
    _max_concurrent = int(cfg.get("max_concurrent_tasks") or 2)
    _per_minute = int(cfg.get("task_per_user_per_minute") or 2)
    _user_times = {}


async def can_accept_user(user_id: int) -> bool:
    """是否允许该用户再提交（分钟内次数限制）。"""
    async with _lock:
        now = time.time()
        if user_id not in _user_times:
            _user_times[user_id] = deque(maxlen=100)
        q = _user_times[user_id]
        while q and q[0] < now - 60:
            q.popleft()
        return len(q) < _per_minute


async def record_user_submit(user_id: int):
    async with _lock:
        if user_id not in _user_times:
            _user_times[user_id] = deque(maxlen=100)
        _user_times[user_id].append(time.time())


async def put_task(task: GalleryTask) -> None:
    await _queue.put(task)


async def get_task() -> GalleryTask:
    return await _queue.get()


def queue_size() -> int:
    return _queue.qsize() if _queue else 0


def max_concurrent() -> int:
    return _max_concurrent
