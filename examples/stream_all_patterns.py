"""Stream each pattern file in patterns/ for 5 seconds."""

import os
from pathlib import Path

from arena_interface import ArenaInterface

PATTERNS_DIR = Path(__file__).resolve().parent.parent / "patterns"
FRAME_RATE = 0
RUNTIME_DURATION = 50  # 50 × 100 ms = 5 s

ip = os.environ.get("ARENA_ETH_IP", "10.103.40.45")
ai = ArenaInterface(debug=True)
ai.set_ethernet_mode(ip_address=ip)

for pat_file in sorted(PATTERNS_DIR.glob("*.pat")):
    print(f"\n--- Streaming {pat_file.name} for 5 s at {FRAME_RATE} Hz ---")
    result = ai.stream_frames(
        pattern_path=str(pat_file),
        frame_rate=FRAME_RATE,
        runtime_duration=RUNTIME_DURATION,
        analog_out_waveform="constant",
        analog_update_rate=1.0,
        analog_frequency=0.0,
    )
    print(f"  frames:  {result['frames']}")
    print(f"  elapsed: {result['elapsed_s']:.2f} s")
    print(f"  rate:    {result['rate_hz']:.1f} Hz")
    print(f"  tx:      {result['tx_mbps']:.2f} Mb/s")
