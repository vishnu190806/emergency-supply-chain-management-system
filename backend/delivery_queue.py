# backend/delivery_queue.py

import heapq
from datetime import datetime, timezone
import logging

# simple logger for queue events — writes timestamps automatically
logger = logging.getLogger("delivery_queue")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # log file in current working directory
    fh = logging.FileHandler("queue.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


class DeliveryQueue:
    def __init__(self):
        self._heap = []
        self._counter = 0
        self.base_priority = {
            "Medical Kit": 10,
            "Water": 6,
            "Food": 4,
            "Blanket": 2,
            "Tarpaulin": 1,
        }

    def _parse_dt(self, v):
        """Parse ISO string or datetime and return a UTC-aware datetime, or None."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return None

    def _compute_priority(self, req, now=None):
        """Compute numeric priority for a request (higher = more urgent)."""
        if now is None:
            now = datetime.now(timezone.utc)

        # Base by type
        base = self.base_priority.get(req.get("supply_type"), 3)

        # Expiry bonus (if expiry_date provided)
        expiry_bonus = 0
        expiry = req.get("expiry_date")
        expiry = self._parse_dt(expiry)
        if expiry:
            days_left = (expiry - now).total_seconds() / 86400.0
            if days_left <= 0:
                expiry_bonus += 0  # already expired -> no bonus
            elif days_left <= 2:
                expiry_bonus += 2
            elif days_left <= 7:
                expiry_bonus += 1

        # Wait-time bonus: +1 per full hour waited up to a cap (e.g., 6)
        timestamp = req.get("timestamp")
        timestamp = self._parse_dt(timestamp)
        hours_waited = 0
        if timestamp:
            hours_waited = max(0, int((now - timestamp).total_seconds() // 3600))
        wait_bonus = min(hours_waited, 6)

        # Distance factor (optional): small boost for nearby locations when priorities tie
        distance_km = req.get("distance_km", None)
        distance_bonus = 0
        if distance_km is not None:
            try:
                d = float(distance_km)
                if d <= 5:
                    distance_bonus = 0.5
                elif d <= 20:
                    distance_bonus = 0.2
            except Exception:
                distance_bonus = 0

        priority = base + expiry_bonus + wait_bonus + distance_bonus
        return float(priority)

    def add_request(self, request):
        """Add a request dict to the queue. Request must contain:

        - id, supply_type, quantity, timestamp (ISO string or datetime)
        optional: expiry_date (ISO/datetime), distance_km (float)
        """
        now = datetime.now(timezone.utc)

        # normalize timestamps to UTC-aware datetime objects (allow blank -> now)
        ts = request.get("timestamp")
        if ts is None or ts == "":
            ts = now
        else:
            ts = self._parse_dt(ts)
        if ts is None:
            ts = now
        request["timestamp"] = ts

        # also normalize expiry if present (so later code can use it directly)
        if "expiry_date" in request:
            request["expiry_date"] = self._parse_dt(request.get("expiry_date"))

        # compute priority
        pr = self._compute_priority(request, now=now)

        # push (neg priority for max-heap effect, timestamp for tie-breaker, counter, request)
        heapq.heappush(self._heap, (-pr, request["timestamp"], self._counter, request))
        self._counter += 1

        # logging
        try:
            ts_iso = request["timestamp"].isoformat()
        except Exception:
            ts_iso = str(request["timestamp"])
        logger.info(
            f"ENQUEUE id={request.get('id')} "
            f"type={request.get('supply_type')} "
            f"priority={pr} ts={ts_iso} dest={request.get('destination')}"
        )

        return pr

    def peek(self):
        """Return the top item (without removing), with computed priority."""
        if not self._heap:
            return None
        pr_neg, ts, cnt, req = self._heap[0]
        return {"priority": -pr_neg, "timestamp": ts, "request": req}

    def pop(self):
        """Remove and return the top request with its computed priority."""
        if not self._heap:
            return None
        pr_neg, ts, cnt, req = heapq.heappop(self._heap)
        pr = -pr_neg

        try:
            ts_iso = ts.isoformat()
        except Exception:
            ts_iso = str(ts)
        logger.info(
            f"POP id={req.get('id')} "
            f"type={req.get('supply_type')} "
            f"priority={pr} ts={ts_iso} dest={req.get('destination')}"
        )

        return {"priority": pr, "timestamp": ts, "request": req}

    def list_all(self):
        """Return a snapshot list of all items sorted by priority (highest first)."""
        items = sorted(self._heap)  # sorted ascending by tuple
        result = []
        for pr_neg, ts, cnt, req in items:
            result.append({"priority": -pr_neg, "timestamp": ts, "request": req})
        # sorted() gives smallest first; we want highest priority first so reverse
        return list(reversed(result))

    def __len__(self):
        return len(self._heap)
