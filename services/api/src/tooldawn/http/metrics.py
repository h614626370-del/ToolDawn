from collections import Counter, deque
from time import perf_counter


class HttpMetrics:
    """Bounded, process-local counters; no paths, user data or credentials."""

    def __init__(self):
        self.total = 0
        self.errors = 0
        self.statuses = Counter()
        self.recent = deque(maxlen=10000)
        self.inflight = 0

    def record(self, status, duration):
        self.total += 1
        self.errors += int(status >= 500)
        self.statuses[str(status // 100) + "xx"] += 1
        self.recent.append((perf_counter(), duration, status))

    def snapshot(self):
        rows = [row for row in self.recent if row[0] >= perf_counter() - 60]
        durations = sorted(row[1] for row in rows)
        return {
            "total": self.total,
            "server_errors": self.errors,
            "statuses": dict(self.statuses),
            "inflight": self.inflight,
            "requests_last_minute": len(rows),
            "p95_ms": round(durations[min(len(durations) - 1, int(len(durations) * 0.95))], 1)
            if durations
            else 0,
        }
