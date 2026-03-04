"""Python interface to the Reiser lab ArenaController."""
import socket
import struct
import time
import serial
import atexit

import cProfile
import pstats


PORT = 62222
PATTERN_HEADER_SIZE = 7
BYTE_COUNT_PER_PANEL_GRAYSCALE = 132
REPEAT_LIMIT = 4
NANOSECONDS_PER_SECOND = 1e9
NANOSECONDS_PER_RUNTIME_DURATION = 1e8
RUNTIME_DURATION_PER_SECOND = 10
MILLISECONDS_PER_SECOND = 1000
SOCKET_TIMEOUT = None
SERIAL_TIMEOUT = None
SERIAL_BAUDRATE = 115200
ANALOG_OUTPUT_VALUE_MIN = 100
ANALOG_OUTPUT_VALUE_MAX = 4095


class ArenaInterface():
    """Python interface to the Reiser lab ArenaController."""
    def __init__(self, debug=False):
        """Initialize a ArenaHost instance."""
        self._debug = debug
        self._serial = None
        self._ethernet_ip_address = ''
        atexit.register(self._exit)

    def _debug_print(self, *args):
        """Print if debug is True."""
        if self._debug:
            print(*args)

    def _exit(self):
        """
        Close the serial connection to provide some clean up.
        """
        if self._serial:
            self._serial.close()

    def _connect_ethernet_socket(self, repeat_count=10, reuse=True):
        """Connect (or reuse) a TCP socket to the firmware's Ethernet server."""
        if not self._ethernet_ip_address:
            raise RuntimeError(
                "Ethernet mode not set. Call set_ethernet_mode(ip) or pass --ethernet IP."
            )

        if reuse and (self._ethernet_socket is not None):
            return self._ethernet_socket

        # Ensure we don't accidentally keep a stale socket around.
        self._close_ethernet_socket()

        last_exc = None
        for _ in range(repeat_count):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Low latency for small request/response commands.
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.settimeout(SOCKET_TIMEOUT)
                s.connect((self._ethernet_ip_address, ETHERNET_SERVER_PORT))

                if reuse:
                    self._ethernet_socket = s
                return s
            except (ConnectionRefusedError, TimeoutError, OSError) as e:
                last_exc = e
                try:
                    s.close()
                except Exception:
                    pass
                # Short backoff; firmware may still be booting.
                time.sleep(0.2)

        raise last_exc if last_exc is not None else ConnectionRefusedError()


    @staticmethod
    def _recv_exact(ethernet_socket: socket.socket, n: int) -> bytes:
        """Receive exactly n bytes from a TCP socket or raise on EOF."""
        data = b""
        while len(data) < n:
            chunk = ethernet_socket.recv(n - len(data))
            if not chunk:
                raise ConnectionError("socket closed while receiving")
            data += chunk
        return data

    def _send_and_receive(self, cmd, ethernet_socket=None):
        """Send a command and wait for a binary response.

        If no socket is provided and we're in Ethernet mode, this reuses a
        persistent TCP connection to avoid per-command connect overhead.
        """
        if self._serial:
            if isinstance(cmd, str):
                self._serial.write(cmd.encode())
            else:
                self._serial.write(cmd)
            resp_len = self._serial.read(1)
            response = resp_len + self._serial.read(int(resp_len[0]))
            return response[3:]

        # Ethernet
        sock = ethernet_socket if (ethernet_socket is not None) else self._connect_ethernet_socket(reuse=True)

        def _do_io(s: socket.socket):
            if isinstance(cmd, str):
                s.sendall(cmd.encode())
            else:
                s.sendall(cmd)

            resp_len = self._recv_exact(s, 1)
            payload = self._recv_exact(s, int(resp_len[0]))
            return (resp_len + payload)[3:]

        # If we're using the persistent socket, allow one reconnect attempt.
        attempts = 1 if (ethernet_socket is not None) else 2
        for _ in range(attempts):
            try:
                return _do_io(sock)
            except (OSError, ConnectionError) as e:
                if ethernet_socket is not None:
                    raise
                self._debug_print(f"socket error ({e}), reconnecting")
                self._close_ethernet_socket()
                sock = self._connect_ethernet_socket(reuse=True)

        raise ConnectionError("failed to send/receive over Ethernet after reconnect")

    def _send_and_receive_stream(self, stream_header, frame_chunked, ethernet_socket):
        """Send a stream frame (header + frame payload) and wait for response."""
        ethernet_socket.sendall(stream_header)
        for chunk in frame_chunked:
            ethernet_socket.sendall(chunk)

        resp_len = self._recv_exact(ethernet_socket, 1)
        payload = self._recv_exact(ethernet_socket, int(resp_len[0]))
        return (resp_len + payload)[3:]

    def set_ethernet_mode(self, ip_address):
        """Set ethernet mode."""
        if self._serial:
            self._serial.close()
        self._serial = None
        self._ethernet_ip_address = ip_address
        self._close_ethernet_socket()
        return True

    def set_serial_mode(self, port, baudrate=SERIAL_BAUDRATE):
        """Set serial mode specifying the serial port."""
        self._close_ethernet_socket()
        self._ethernet_ip_address = None
        if self._serial:
            self._serial.close()

        self._serial = serial.Serial()
        self._serial.port = port
        self._serial.baudrate = baudrate
        self._serial.timeout = SERIAL_TIMEOUT
        self._serial.open()
        return self._serial.is_open


    def _close_ethernet_socket(self):
        """Close and forget the persistent Ethernet socket (if any)."""
        if self._ethernet_socket is not None:
            try:
                self._ethernet_socket.close()
            except OSError:
                pass
        self._ethernet_socket = None

    def close(self):
        """Close any open transport (serial or Ethernet)."""
        if self._serial:
            try:
                self._serial.close()
            except OSError:
                pass
        self._serial = None
        self._close_ethernet_socket()

    def all_off(self):
        """Turn all panels off."""
        self._send_and_receive(b'\x01\x00')

    def display_reset(self):
        """Reset arena."""
        self._send_and_receive(b'\x01\x01')

    def switch_grayscale(self, grayscale_index):
        """Switches grayscale value. grayscale_index: 0=binary, 1=grayscale"""
        cmd_bytes = struct.pack('<BBB', 0x02, 0x06, grayscale_index)
        self._send_and_receive(cmd_bytes)

    def play_pattern(self, pattern_id, frame_rate, runtime_duration, initial_frame_index=0):
        """Play pattern with constant frame rate."""
        control_mode = 0x02
        gain = 0x10 # dummy value
        cmd_bytes = struct.pack('<BBBHhHhH',
                                0x0c,
                                0x08,
                                control_mode,
                                pattern_id,
                                frame_rate,
                                initial_frame_index,
                                gain,
                                runtime_duration)
        runtime_duration_s = (runtime_duration * 1.0) / RUNTIME_DURATION_PER_SECOND
        runtime_duration_ms = int(runtime_duration_s * MILLISECONDS_PER_SECOND)
        self._debug_print('runtime_duration_ms: ', runtime_duration_ms)
        ethernet_socket = self._connect_ethernet_socket()
        self._send_and_receive(cmd_bytes, ethernet_socket)

        while True:
            self._debug_print('waiting for playing pattern end response...')
            time.sleep(1)
            response = self._read(ethernet_socket, 1)
            if len(response) == 1:
                response += self._read(ethernet_socket, int(response[0]))
                break
        self._debug_print('response: ', response)

    def play_pattern_analog_closed_loop(self, pattern_id, gain, runtime_duration, initial_frame_index=0):
        """Play pattern with frame rate set by analog signal."""
        control_mode = 0x04
        frame_rate = 0x00 # dummy value
        cmd_bytes = struct.pack('<BBBHhHhH',
                                0x0c,
                                0x08,
                                control_mode,
                                pattern_id,
                                frame_rate,
                                initial_frame_index,
                                gain,
                                runtime_duration)
        runtime_duration_s = (runtime_duration * 1.0) / RUNTIME_DURATION_PER_SECOND
        runtime_duration_ms = int(runtime_duration_s * MILLISECONDS_PER_SECOND)
        self._debug_print('runtime_duration_ms: ', runtime_duration_ms)
        ethernet_socket = self._connect_ethernet_socket()
        self._send_and_receive(cmd_bytes, ethernet_socket)

        while True:
            self._debug_print('waiting for playing pattern end response...')
            time.sleep(1)
            response = self._read(ethernet_socket, 1)
            if len(response) == 1:
                response += self._read(ethernet_socket, int(response[0]))
                break
        self._debug_print('response: ', response)

    def show_pattern_frame(self, pattern_id, frame_index, ethernet_socket=None):
        """Show pattern frame."""
        control_mode = 0x03
        frame_rate = 0
        gain = 0x10 # dummy value
        runtime_duration = 0
        cmd_bytes = struct.pack('<BBBHhHhH',
                                0x0c,
                                0x08,
                                control_mode,
                                pattern_id,
                                frame_rate,
                                frame_index,
                                gain,
                                runtime_duration)
        self._send_and_receive(cmd_bytes, ethernet_socket)

    def update_pattern_frame(self, frame_index, ethernet_socket=None):
        """Update pattern frame."""
        cmd_bytes = struct.pack('<BBH',
                                0x03,
                                0x70,
                                frame_index)
        self._send_and_receive(cmd_bytes, ethernet_socket)

    def profile_stream_pattern_frame_indicies(self, pattern_id, frame_index_min, frame_index_max, frame_rate, runtime_duration):
        """Profile stream frame indicies in a loop at some rate for some duration."""
        # Profile the execution of another_function
        profiler = cProfile.Profile()
        profiler.enable()
        self.stream_pattern_frame_indicies(pattern_id, frame_index_min, frame_index_max, frame_rate, runtime_duration)
        profiler.disable()

        # Create a Stats object and print the report
        stats = pstats.Stats(profiler)
        stats.sort_stats('tottime') # Sort by total time spent in a function (excluding calls to sub-functions)
        stats.print_stats()

    def stream_pattern_frame_indicies(self, pattern_id, frame_index_min, frame_index_max, frame_rate, runtime_duration):
        """Stream frame indicies in a loop at some rate for some duration."""
        self._debug_print('frame_rate: ', frame_rate)
        if frame_rate != 0:
            frame_period_ns = int(NANOSECONDS_PER_SECOND / frame_rate)
        runtime_duration_ns = int(NANOSECONDS_PER_RUNTIME_DURATION * runtime_duration)
        self._debug_print('frame_period_ns: ', frame_period_ns)
        self._debug_print('runtime_duration_ns: ', runtime_duration_ns)
        frames_displayed_count = 0
        frames_to_display_count = int((frame_rate * runtime_duration) / RUNTIME_DURATION_PER_SECOND)
        ethernet_socket = self._connect_ethernet_socket()
        self.show_pattern_frame(pattern_id, frame_index_min, ethernet_socket)
        stream_frames_start_time = time.time_ns()
        while frames_displayed_count < frames_to_display_count:
            pattern_start_time = time.time_ns()
            for frame_index in range(frame_index_min, frame_index_max+1):
                self.update_pattern_frame(frame_index, ethernet_socket)
                frames_displayed_count= frames_displayed_count + 1
                seconds_elapsed = int((time.time_ns() - stream_frames_start_time) / NANOSECONDS_PER_SECOND)
                self._debug_print('frames streamed: ', frames_displayed_count, ':', frames_to_display_count, seconds_elapsed)
                while (time.time_ns() - pattern_start_time) < ((frame_index + 1) * frame_period_ns):
                    pass
        stream_frames_stop_time = time.time_ns()
        duration_s = (stream_frames_stop_time - stream_frames_start_time) / NANOSECONDS_PER_SECOND
        print('stream frames duration:', duration_s)
        frame_rate_actual = frames_displayed_count / duration_s
        print('frame rate requested: ', frame_rate, ', frame rate actual:', frame_rate_actual)
        self.all_off()

    def set_refresh_rate(self, refresh_rate):
        """Set refresh rate in Hz."""
        cmd_bytes = struct.pack('<BBH', 0x03, 0x16, refresh_rate)
        self._send_and_receive(cmd_bytes)

    def get_ethernet_ip_address(self):
        """Get Ethernet IP address."""
        return self._send_and_receive(b'\x01\x66')

    def all_on(self):
        """Turn all panels on."""
        self._send_and_receive(b'\x01\xff')

    def stream_frame(self, path, frame_index, analog_output_value=0):
        """Stream frame in pattern file."""
        self._debug_print('pattern path: ', path)
        with open(path, mode='rb') as f:
            content = f.read()
            pattern_header = struct.unpack('<HHBBB', content[:PATTERN_HEADER_SIZE])
            self._debug_print('pattern header: ', pattern_header)
            frames = content[PATTERN_HEADER_SIZE:]
            frame_count = pattern_header[0] * pattern_header[1]
            self._debug_print('frame_count: ', frame_count)
            if frame_index < 0:
                frame_index = 0
            if frame_index > (frame_count - 1):
                frame_index = frame_count - 1
            self._debug_print('frame_index: ', frame_index)
            frame_len = len(frames)//frame_count
            frame_start = frame_index * frame_len
            # self._debug_print('frame_start: ', frame_start)
            frame_end = frame_start + frame_len
            # self._debug_print('frame_end: ', frame_end)
            frame = frames[frame_start:frame_end]
            data_len = len(frame)
            # self._debug_print('data_len: ', data_len)
            frame_header = struct.pack('<BHHH', 0x32, data_len, analog_output_value,  0)
            self._debug_print('frame header: ', frame_header)
            message = frame_header + frame
            self._debug_print('len(message): ', len(message))
            # self._debug_print('message: ', message)
            self._send_and_receive(message)

    def profile_stream_frames(self, path, frame_rate, runtime_duration):
        """Profile stream frames in pattern file at some frame rate for some duration."""
        # Profile the execution of another_function
        profiler = cProfile.Profile()
        profiler.enable()
        self.stream_frames(path, frame_rate, runtime_duration)
        profiler.disable()

        # Create a Stats object and print the report
        stats = pstats.Stats(profiler)
        stats.sort_stats('tottime') # Sort by total time spent in a function (excluding calls to sub-functions)
        stats.print_stats()

    def _map_frame_index_to_analog_value(self, frame_index, frame_count):
        return int(ANALOG_OUTPUT_VALUE_MIN + (frame_index * (ANALOG_OUTPUT_VALUE_MAX - ANALOG_OUTPUT_VALUE_MIN)) / frame_count)

    def stream_frames(
            self,
            pattern_path,
            frame_rate,
            runtime_duration,
            analog_out_waveform,
            analog_update_rate,
            analog_frequency,
            stream_cmd_coalesced=False,
            progress_interval_s=1.0,
    ):
        """Stream a pattern file's frames at a fixed rate for a fixed duration.

        Returns a dict with basic host-side throughput stats.
        """
        # Read pattern file: [uint32 frame_size][frame0][frame1]...
        with open(pattern_path, 'rb') as f:
            frame_size = struct.unpack('<I', f.read(4))[0]
            file_size = os.path.getsize(pattern_path)
            num_frames = int((file_size - 4) / frame_size)
            frames = [f.read(frame_size) for _ in range(num_frames)]

        frames_total = int(runtime_duration * frame_rate)
        frame_period_ns = int((1 / frame_rate) * 1e9)

        analog_update_period_ns = int((1 / analog_update_rate) * 1e9)
        analog_start_time_ns = time.perf_counter_ns()

        analog_amplitude = (2 ** 16) / 2 - 1
        analog_offset = (2 ** 16) / 2

        def analog_waveform_for(name):
            if name == 'sin':
                return np.sin
            elif name == 'square':
                return lambda x: np.sign(np.sin(x))
            elif name == 'sawtooth':
                return lambda x: 2 * (x / (2 * np.pi) - np.floor(1 / 2 + x / (2 * np.pi)))
            elif name == 'triangle':
                return lambda x: 2 * np.abs(2 * (x / (2 * np.pi) - np.floor(1 / 2 + x / (2 * np.pi)))) - 1
            elif name == 'constant':
                return lambda x: 0
            else:
                raise ValueError(f'Invalid analog output waveform: {name}')

        ethernet_socket = self._connect_ethernet_socket(reuse=True)

        bytes_sent = 0
        frames_streamed = 0

        start_time_ns = time.perf_counter_ns()
        next_progress_ns = None
        if progress_interval_s and (progress_interval_s > 0):
            next_progress_ns = start_time_ns + int(progress_interval_s * 1e9)

        for i in range(frames_total):
            frame_index = i % num_frames
            frame = frames[frame_index]

            # Analog output update (optional)
            if (time.perf_counter_ns() - analog_start_time_ns) > (i * analog_update_period_ns):
                analog_phase = (i / analog_update_rate) * analog_frequency * 2 * np.pi
                analog_output_value = analog_amplitude * analog_waveform_for(analog_out_waveform)(analog_phase) + analog_offset
                # Ensure this is an int in-range for uint16.
                analog_output_value = int(max(0, min(65535, round(float(analog_output_value)))))
            else:
                analog_output_value = 0

            # Stream frame header: cmd(0x32), data_len(uint16), analog(uint16), reserved(uint16)
            data_len = len(frame)
            stream_header = struct.pack('<BHHH', 0x32, data_len, analog_output_value, 0)

            if stream_cmd_coalesced:
                self._send_and_receive(stream_header + frame, ethernet_socket)
            else:
                # Chunk the frame payload for better control over send sizes.
                frame_chunked = [frame[i:i + CHUNK_SIZE] for i in range(0, len(frame), CHUNK_SIZE)]
                self._send_and_receive_stream(stream_header, frame_chunked, ethernet_socket)

            frames_streamed += 1
            bytes_sent += (len(stream_header) + data_len)

            # Progress (throttled)
            if next_progress_ns is not None:
                now_ns = time.perf_counter_ns()
                if now_ns >= next_progress_ns:
                    elapsed_s = (now_ns - start_time_ns) / 1e9
                    rate_hz = frames_streamed / elapsed_s if elapsed_s > 0 else 0.0
                    print(f'progress: {frames_streamed}/{frames_total} frames ({rate_hz:.1f} Hz)')
                    next_progress_ns += int(progress_interval_s * 1e9)

            # Rate limiting (busy-wait)
            while (time.perf_counter_ns() - start_time_ns) < ((i + 1) * frame_period_ns):
                pass

        # End the mode
        self._send_and_receive(bytes([1, 0]), ethernet_socket)

        elapsed_s = (time.perf_counter_ns() - start_time_ns) / 1e9
        rate_hz = frames_streamed / elapsed_s if elapsed_s > 0 else 0.0
        mbps = (bytes_sent * 8) / (elapsed_s * 1e6) if elapsed_s > 0 else 0.0
        print(f'frames streamed: {frames_streamed}, elapsed_s: {elapsed_s:.3f}, rate: {rate_hz:.1f} Hz, tx: {mbps:.2f} Mb/s')

        return {
            "frames": frames_streamed,
            "elapsed_s": elapsed_s,
            "rate_hz": rate_hz,
            "bytes_sent": bytes_sent,
            "tx_mbps": mbps,
        }

    def all_off_str(self):
        """Turn all panels off with string."""
        self._send_and_receive('ALL_OFF')

    def all_on_str(self):
        """Turn all panels on with string."""
        self._send_and_receive('ALL_ON')
