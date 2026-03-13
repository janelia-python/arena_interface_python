import time

from arena_interface import ArenaInterface

ai = ArenaInterface(debug=True)
ai.set_ethernet_mode(ip_address="10.103.40.45")

# Measure time for play_pattern call
start_time = time.time()
ai.play_pattern(pattern_id=532, frame_rate=20, runtime_duration=10)
end_time = time.time()

duration = end_time - start_time
print(f"play_pattern() duration: {duration:.6f} seconds")
