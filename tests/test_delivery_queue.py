import math
from datetime import datetime, timedelta, timezone

from backend.delivery_queue import DeliveryQueue


def make_now():
  # fixed reference time so tests are deterministic
  return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_medical_higher_than_food():
  dq = DeliveryQueue()
  now = make_now()

  req_med = {
      "id": "M1",
      "supply_type": "Medical Kit",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 10,
  }

  req_food = {
      "id": "F1",
      "supply_type": "Food",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 10,
  }

  pr_med = dq._compute_priority(req_med, now=now)
  pr_food = dq._compute_priority(req_food, now=now)

  assert pr_med > pr_food


def test_expiring_soon_gets_boost():
  dq = DeliveryQueue()
  now = make_now()

  # same type, different expiry
  base = {
      "id": "X",
      "supply_type": "Food",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 10,
  }

  req_far = base | {
      "expiry_date": (now + timedelta(days=10)).isoformat()
  }
  req_soon = base | {
      "expiry_date": (now + timedelta(days=1)).isoformat()
  }

  pr_far = dq._compute_priority(req_far, now=now)
  pr_soon = dq._compute_priority(req_soon, now=now)

  assert pr_soon > pr_far


def test_waiting_longer_increases_priority():
  dq = DeliveryQueue()
  now = make_now()

  recent = {
      "id": "R",
      "supply_type": "Water",
      "quantity": 1,
      "timestamp": (now - timedelta(hours=1)).isoformat(),
  }

  old = {
      "id": "O",
      "supply_type": "Water",
      "quantity": 1,
      "timestamp": (now - timedelta(hours=5)).isoformat(),
  }

  pr_recent = dq._compute_priority(recent, now=now)
  pr_old = dq._compute_priority(old, now=now)

  assert pr_old > pr_recent


def test_distance_bonus_for_nearby():
  dq = DeliveryQueue()
  now = make_now()

  near = {
      "id": "N",
      "supply_type": "Blanket",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 3,
  }

  far = {
      "id": "F",
      "supply_type": "Blanket",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 50,
  }

  pr_near = dq._compute_priority(near, now=now)
  pr_far = dq._compute_priority(far, now=now)

  assert pr_near > pr_far


def test_queue_orders_by_priority():
  dq = DeliveryQueue()
  now = make_now()

  # lower priority
  dq.add_request({
      "id": "LOW",
      "supply_type": "Blanket",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 20,
  })

  # higher priority
  dq.add_request({
      "id": "HIGH",
      "supply_type": "Medical Kit",
      "quantity": 1,
      "timestamp": now.isoformat(),
      "distance_km": 20,
  })

  top = dq.pop()
  assert top is not None
  assert top["request"]["id"] == "HIGH"
  assert math.isfinite(top["priority"])
