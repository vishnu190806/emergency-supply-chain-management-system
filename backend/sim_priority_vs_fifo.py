# sim_priority_vs_fifo_fixed.py
"""
Corrected simulation comparing Priority queue vs FIFO.
- Anchors all virtual timestamps to a single `anchor` to ensure determinism.
- Uses identical arrival sequences and service-time streams for fair comparison.
- Produces two PNGs: mean_wait_vs_rate.png and p95_wait_vs_rate.png

Usage:
    python sim_priority_vs_fifo_fixed.py
"""

import heapq
import random
import math
import statistics
from collections import deque
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt

# ---------------------------
# Priority computation (same rules as DeliveryQueue)
# ---------------------------
BASE_PRIORITY = {
    'Medical Kit': 10,
    'Water': 6,
    'Food': 4,
    'Blanket': 2,
    'Tarpaulin': 1
}

def compute_priority(req, now_dt):
    """Compute numeric priority for request (float). now_dt is a timezone-aware datetime."""
    base = BASE_PRIORITY.get(req['supply_type'], 3)

    # expiry bonus
    expiry_bonus = 0.0
    expiry = req.get('expiry_date')  # expected as aware datetime or None
    if expiry:
        days_left = (expiry - now_dt).total_seconds() / 86400.0
        if days_left <= 0:
            expiry_bonus += 0
        elif days_left <= 2:
            expiry_bonus += 2
        elif days_left <= 7:
            expiry_bonus += 1

    # wait bonus (compute using request timestamp)
    ts = req.get('timestamp')
    hours_waited = 0
    if ts:
        hours_waited = max(0, int((now_dt - ts).total_seconds() // 3600))
    wait_bonus = min(hours_waited, 6)

    # distance
    distance_bonus = 0.0
    d = req.get('distance_km')
    if d is not None:
        try:
            dd = float(d)
            if dd <= 5:
                distance_bonus = 0.5
            elif dd <= 20:
                distance_bonus = 0.2
        except:
            distance_bonus = 0.0

    return float(base + expiry_bonus + wait_bonus + distance_bonus)

# ---------------------------
# Workload generator (anchored)
# ---------------------------
def generate_arrivals(total_time_s, arrival_rate, seed=1, supply_mix=None, anchor=None):
    """
    Generate arrival events over [0, total_time_s).
    arrival_rate = lambda (events per second).
    Returns list of (arrival_time_seconds, request_dict).
    """
    rnd = random.Random(seed)
    if anchor is None:
        anchor = datetime.now(timezone.utc)
    t = 0.0
    arrivals = []
    if supply_mix is None:
        supply_mix = ['Medical Kit','Water','Food','Blanket','Tarpaulin']

    while t < total_time_s:
        if arrival_rate <= 0:
            break
        inter = rnd.expovariate(arrival_rate)
        t += inter
        if t >= total_time_s:
            break
        s = rnd.choice(supply_mix)
        # expiry selection
        if s == 'Medical Kit':
            expiry_days = rnd.choice([0.5, 1, 3, 10])
        elif s == 'Water':
            expiry_days = rnd.choice([1, 3, 7, 20])
        else:
            expiry_days = rnd.choice([3, 7, 30])
        expiry_dt = anchor + timedelta(days=expiry_days)
        timestamp_dt = anchor + timedelta(seconds=t)
        req = {
            'id': f"A{int(t*1000)}_{rnd.randint(0,999)}",
            'supply_type': s,
            'quantity': rnd.randint(1,50),
            'timestamp': timestamp_dt,
            'expiry_date': expiry_dt,
            'distance_km': rnd.choice([1,3,8,12,25])
        }
        arrivals.append((t, req))
    return arrivals

# ---------------------------
# Helper: percentile (robust)
# ---------------------------
def percentile(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s)-1) * (p/100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return d0 + d1

# ---------------------------
# Simulators
# ---------------------------
def simulate(arrivals, service_rate, discipline='priority', seed=42, anchor=None):
    """
    Simulate given arrival list [(arrival_time_seconds, req), ...]
    service_rate: mu (services per second) -> mean service time = 1/mu
    discipline: 'priority' or 'fifo'
    Returns metrics dict with per-request waits and other stats.
    """
    rnd = random.Random(seed)
    if anchor is None:
        anchor = datetime.now(timezone.utc)

    now = 0.0
    next_arrival_index = 0
    server_busy_until = 0.0
    server_busy = False
    current_request = None

    if discipline == 'priority':
        heap = []  # (-priority, counter, enqueue_time, req)
        counter = 0
    else:
        q = deque()

    records = []

    # Pre-generate service times deterministically (enough for the run)
    est_services = max(1000, len(arrivals)*3)
    service_times = [rnd.expovariate(service_rate) for _ in range(est_services)]
    service_iter = iter(service_times)

    while True:
        next_arrival_time = arrivals[next_arrival_index][0] if next_arrival_index < len(arrivals) else math.inf
        next_service_completion = server_busy_until if server_busy else math.inf
        next_event_time = min(next_arrival_time, next_service_completion)

        if next_event_time == math.inf:
            # no more events
            break

        now = next_event_time

        # handle arrivals at this time (could be multiple very close)
        while next_arrival_index < len(arrivals) and arrivals[next_arrival_index][0] <= now + 1e-12:
            atime, req = arrivals[next_arrival_index]
            now_dt = anchor + timedelta(seconds=atime)
            priority = compute_priority(req, now_dt)
            if discipline == 'priority':
                heapq.heappush(heap, (-priority, counter, atime, req))
                counter += 1
            else:
                q.append((atime, req))
            next_arrival_index += 1

        # if server free, start next service if queue not empty
        if not server_busy:
            next_item = None
            if discipline == 'priority' and heap:
                pr_neg, cnt, enq_t, req = heapq.heappop(heap)
                priority_at_enqueue = -pr_neg
                next_item = (enq_t, req, priority_at_enqueue)
            elif discipline == 'fifo' and q:
                enq_t, req = q.popleft()
                priority_at_enqueue = compute_priority(req, anchor + timedelta(seconds=enq_t))
                next_item = (enq_t, req, priority_at_enqueue)

            if next_item:
                enq_t, req, priority_at_enqueue = next_item
                try:
                    st = next(service_iter)
                except StopIteration:
                    st = rnd.expovariate(service_rate)
                server_busy = True
                server_busy_until = now + st
                current_request = {
                    'req': req,
                    'enq_t': enq_t,
                    'priority_at_enqueue': priority_at_enqueue,
                    'service_start': now,
                    'service_time': st
                }
            else:
                # nothing to process; loop will advance to next arrival
                if next_arrival_time == math.inf:
                    break
                continue
        else:
            # service completion just happened at 'now'
            dispatch_time = now
            rec = {
                'id': current_request['req']['id'],
                'supply_type': current_request['req']['supply_type'],
                'enqueue_time': current_request['enq_t'],
                'dispatch_time': dispatch_time,
                'wait_sec': max(0.0, dispatch_time - current_request['enq_t']),
                'priority_at_enqueue': current_request['priority_at_enqueue']
            }
            records.append(rec)
            # free server
            server_busy = False
            current_request = None
            server_busy_until = 0.0

    # metrics
    wait_times = [r['wait_sec'] for r in records]
    mean_wait = statistics.mean(wait_times) if wait_times else 0.0
    p95 = percentile(wait_times, 95) if wait_times else 0.0
    urgent_waits = [r['wait_sec'] for r in records if r['supply_type'] == 'Medical Kit']
    mean_wait_urgent = statistics.mean(urgent_waits) if urgent_waits else 0.0
    sla = 3600.0
    urgent_within_sla = sum(1 for w in urgent_waits if w <= sla)
    urgent_fraction = urgent_within_sla / len(urgent_waits) if urgent_waits else 0.0

    return {
        'mean_wait': mean_wait,
        'p95_wait': p95,
        'mean_wait_urgent': mean_wait_urgent,
        'urgent_fraction': urgent_fraction,
        'count': len(records),
        'all_waits': wait_times
    }

# ---------------------------
# Runner: sweep arrival rates and compare
# ---------------------------
def run_sweep():
    total_time_s = 3600.0    # 1 hour simulation for smoother stats
    service_rate = 1.0/30.0  # mean service time 30s -> mu = 1/30
    arrival_rates = [0.02, 0.03, 0.04, 0.05, 0.06]  # events per second
    # Prepare lists for plotting
    pr_means = []
    fifo_means = []
    pr_p95 = []
    fifo_p95 = []
    labels = []

    # single anchor for the entire sweep (ensures deterministic timestamps)
    anchor = datetime.now(timezone.utc)

    for lam in arrival_rates:
        arrivals = generate_arrivals(total_time_s, lam, seed=123, anchor=anchor)
        # use identical seeds and anchor to keep fair comparison
        pr_metrics = simulate(arrivals, service_rate, discipline='priority', seed=999, anchor=anchor)
        fifo_metrics = simulate(arrivals, service_rate, discipline='fifo', seed=999, anchor=anchor)

        print(f"Rate {lam:.3f}/s | priority mean_wait={pr_metrics['mean_wait']:.1f}s p95={pr_metrics['p95_wait']:.1f}s | "
              f"fifo mean_wait={fifo_metrics['mean_wait']:.1f}s p95={fifo_metrics['p95_wait']:.1f}s | "
              f"count={pr_metrics['count']}")

        pr_means.append(pr_metrics['mean_wait'])
        fifo_means.append(fifo_metrics['mean_wait'])
        pr_p95.append(pr_metrics['p95_wait'])
        fifo_p95.append(fifo_metrics['p95_wait'])
        labels.append(lam)

    # plot mean waits
    plt.figure(figsize=(9,5))
    plt.plot(labels, pr_means, marker='o', label='Priority')
    plt.plot(labels, fifo_means, marker='o', label='FIFO')
    plt.xlabel('Arrival rate (events/sec)')
    plt.ylabel('Mean wait (s)')
    plt.title('Mean wait vs arrival rate')
    plt.legend()
    plt.grid(True)
    plt.savefig('mean_wait_vs_rate.png', dpi=150)
    print("Saved mean_wait_vs_rate.png")

    # plot p95 waits
    plt.figure(figsize=(9,5))
    plt.plot(labels, pr_p95, marker='o', label='Priority')
    plt.plot(labels, fifo_p95, marker='o', label='FIFO')
    plt.xlabel('Arrival rate (events/sec)')
    plt.ylabel('95th percentile wait (s)')
    plt.title('95th percentile wait vs arrival rate')
    plt.legend()
    plt.grid(True)
    plt.savefig('p95_wait_vs_rate.png', dpi=150)
    print("Saved p95_wait_vs_rate.png")

if __name__ == "__main__":
    run_sweep()