"""Show 5 patterns for 5 seconds each using show_pattern_frame.

For each pattern, send as many show_pattern_frame commands as possible
at a target rate of 300 Hz with random frame indices between 1 and 15.
"""

import os
import random
import time

from arena_interface import ArenaInterface

PATTERN_IDS = [1] + random.sample(range(2, 10), 4)
DURATION_S = 5.0
TARGET_RATE_HZ = 300
FRAME_INDEX_MIN = 1
FRAME_INDEX_MAX = 15

ip = os.environ.get("ARENA_ETH_IP", "10.103.40.45")
ai = ArenaInterface(debug=True)
ai.set_ethernet_mode(ip_address=ip)

for pat_id in PATTERN_IDS:
    print(f"\n--- Showing pattern {pat_id} for {DURATION_S} s at {TARGET_RATE_HZ} Hz ---")
    interval = 1.0 / TARGET_RATE_HZ
    count = 0
    t_start = time.perf_counter()
    deadline = t_start + DURATION_S

    while True:
        t_now = time.perf_counter()
        if t_now >= deadline:
            break
        frame_idx = random.randint(FRAME_INDEX_MIN, FRAME_INDEX_MAX)
        ai.show_pattern_frame(pattern_id=pat_id, frame_index=frame_idx)
        count += 1
        # spin-wait until next slot
        next_time = t_start + count * interval
        while time.perf_counter() < next_time:
            pass

    elapsed = time.perf_counter() - t_start
    actual_hz = count / elapsed if elapsed > 0 else 0
    print(f"  Pattern {pat_id}: {count} frames in {elapsed:.2f} s ({actual_hz:.1f} Hz)")
