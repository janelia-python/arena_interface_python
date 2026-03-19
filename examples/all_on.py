import time

from arena_interface import ArenaInterface

ai = ArenaInterface(debug=True)
ai.set_ethernet_mode(ip_address="10.103.40.45")

start_time = time.time()
ai.all_on()
end_time = time.time()
duration = end_time - start_time

time.sleep(5)
ai.all_off()

print(f"Duration of all_on() call: {duration:.6f} seconds")
