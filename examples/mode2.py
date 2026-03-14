"""Play 5 patterns for 5 seconds each using play_pattern.

Pattern 1 runs at 300 fps; the rest at random rates between 10 and 300 fps.
The 4 additional patterns are chosen randomly from IDs 2–700.
"""

import os
import random

from arena_interface import ArenaInterface

PATTERN_IDS = [1] + random.sample(range(2, 701), 4)
RUNTIME_DURATION = 50  # 50 × 100 ms = 5 s

ip = os.environ.get("ARENA_ETH_IP", "10.103.40.45")
ai = ArenaInterface(debug=True)
ai.set_ethernet_mode(ip_address=ip)

for pat_id in PATTERN_IDS:
    fps = 300 if pat_id == PATTERN_IDS[0] else random.randint(10, 300)
    print(f"\n--- Playing pattern {pat_id} at {fps} fps for 5 s ---")
    ai.play_pattern(
        pattern_id=pat_id,
        frame_rate=fps,
        runtime_duration=RUNTIME_DURATION,
    )
    print(f"  Pattern {pat_id} done.")
