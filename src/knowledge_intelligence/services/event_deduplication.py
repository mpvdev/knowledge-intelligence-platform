from datetime import UTC, datetime, timedelta
from threading import Lock


class EventDeduplicationService:
    """Track recently accepted Slack event IDs."""

    def __init__(
        self,
        retention: timedelta = timedelta(minutes=10),
    ) -> None:
        self._retention = retention
        self._events: dict[str, datetime] = {}
        self._lock = Lock()

    def accept(self, event_id: str) -> bool:
        now = datetime.now(UTC)

        with self._lock:
            self._remove_expired(now)

            if event_id in self._events:
                return False

            self._events[event_id] = now
            return True

    def _remove_expired(self, now: datetime) -> None:
        expired = [
            event_id
            for event_id, recorded_at in self._events.items()
            if now - recorded_at > self._retention
        ]

        for event_id in expired:
            del self._events[event_id]
