import asyncio
from typing import Optional

_queues: dict[str, asyncio.Queue] = {}


def create_run_queue(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues[run_id] = q
    return q


def get_run_queue(run_id: str) -> Optional[asyncio.Queue]:
    return _queues.get(run_id)


async def push_event(run_id: str, event: Optional[dict]):
    """Pass None as sentinel to signal pipeline end."""
    q = _queues.get(run_id)
    if q is not None:
        await q.put(event)
        
#"123":[{"agent":"code_reader","status":"running","msg":"Reading code..."},{"agent":"code_reader","status":"done","msg":"Code read successfully"}]

def remove_run_queue(run_id: str):
    _queues.pop(run_id, None)
