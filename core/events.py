import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List


class EventBus:
    def __init__(self, max_history: int = 100):
        self._subscribers: List[asyncio.Queue] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history

    def publish(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "type": event_type,
            "timestamp": int(time.time() * 1000),
            "time_str": time.strftime("%H:%M:%S"),
            "data": data,
        }
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Notify all active SSE listeners
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except Exception:
                pass

        return event

    async def subscribe(self) -> AsyncGenerator[str, None]:
        q = asyncio.Queue()
        self._subscribers.append(q)
        try:
            # Yield initial connect event
            init_event = {
                "type": "CONNECTED",
                "timestamp": int(time.time() * 1000),
                "time_str": time.strftime("%H:%M:%S"),
                "data": {"message": "Event stream connected"},
            }
            yield f"data: {json.dumps(init_event)}\n\n"

            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def clear(self):
        self._history.clear()


event_bus = EventBus()
