"""Python interface and CLI for the Reiser Lab ArenaController."""
from __future__ import annotations

import atexit
import cProfile
import datetime
import json
import math
import platform
import pstats
import re
import socket
import statistics
import struct
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Callable

try:
    import serial
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal environments
    serial = None


ETHERNET_SERVER_PORT = 62222
# Backwards-compat alias (older code may import PORT)
PORT = ETHERNET_SERVER_PORT
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
BENCH_IO_TIMEOUT_S = 5.0

# Chunk size used for optional STREAM_FRAME chunked sends.
# Keep this comfortably below typical MTU to avoid excessive fragmentation.
CHUNK_SIZE = 4096

StatusCallback = Callable[[str], None]


class ArenaInterface:
    """Python interface to the Reiser lab ArenaController."""

    def __init__(
        self,
        debug: bool = False,
        *,
        tcp_nodelay: bool = True,
        tcp_quickack: bool = True,
        keepalive: bool = True,
        socket_timeout_s: float | None = SOCKET_TIMEOUT,
        serial_timeout_s: float | None = SERIAL_TIMEOUT,
    ):
        """Initialize an ArenaInterface instance."""
        self._debug = bool(debug)
        self._serial = None
        self._ethernet_ip_address = ''
        self._ethernet_socket: socket.socket | None = None
        self._socket_reconnects: int = 0
        self._socket_last_error: str | None = None
        self._tcp_nodelay = bool(tcp_nodelay)
        self._tcp_quickack_requested = bool(tcp_quickack)
        self._tcp_quickack_supported = hasattr(socket, "TCP_QUICKACK")
        self._tcp_quickack_last_applied = False
        self._tcp_quickack_apply_errors = 0
        self._keepalive = bool(keepalive)
        self._socket_timeout_s = self._coerce_timeout(socket_timeout_s)
        self._serial_timeout_s = self._coerce_timeout(serial_timeout_s)
        atexit.register(self._exit)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _debug_print(self, *args):
        """Print if debug is True."""
        if self._debug:
            print(*args)

    @staticmethod
    def _coerce_timeout(timeout_s: float | None) -> float | None:
        """Normalize timeout inputs.

        A value of ``None`` or ``<= 0`` means "block indefinitely".
        """
        if timeout_s is None:
            return None
        timeout = float(timeout_s)
        if timeout <= 0:
            return None
        return timeout

    @staticmethod
    def _utc_now_iso() -> str:
        """Return the current UTC time in ISO-8601 format."""
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _bench_emit_status(self, status_callback: StatusCallback | None, message: str) -> None:
        """Emit a benchmark status line, if requested."""
        if status_callback is not None:
            status_callback(str(message))

    def _exit(self):
        """
        Close the serial connection to provide some clean up.
        """
        try:
            self.close()
        except Exception:
            # Best-effort cleanup only.
            pass

    def set_transport_timeouts(
        self,
        *,
        socket_timeout_s: float | None,
        serial_timeout_s: float | None,
    ) -> None:
        """Set default transport timeouts for newly opened and persistent links."""
        self._socket_timeout_s = self._coerce_timeout(socket_timeout_s)
        self._serial_timeout_s = self._coerce_timeout(serial_timeout_s)

        if self._ethernet_socket is not None:
            try:
                self._ethernet_socket.settimeout(self._socket_timeout_s)
            except OSError:
                pass

        if self._serial is not None:
            self._serial.timeout = self._serial_timeout_s

    @contextmanager
    def temporary_transport_timeouts(
        self,
        *,
        socket_timeout_s: float | None,
        serial_timeout_s: float | None,
    ):
        """Temporarily override transport timeouts within a context."""
        prev_socket_timeout_s = self._socket_timeout_s
        prev_serial_timeout_s = self._serial_timeout_s
        self.set_transport_timeouts(
            socket_timeout_s=socket_timeout_s,
            serial_timeout_s=serial_timeout_s,
        )
        try:
            yield
        finally:
            self.set_transport_timeouts(
                socket_timeout_s=prev_socket_timeout_s,
                serial_timeout_s=prev_serial_timeout_s,
            )

    @staticmethod
    def _format_exception(exc: BaseException) -> str:
        """Return a compact exception description for logs/results."""
        return f"{type(exc).__name__}: {exc}"

    def _safe_all_off(
        self,
        *,
        status_callback: StatusCallback | None = None,
        context: str = "bench cleanup",
    ) -> str | None:
        """Best-effort ALL_OFF used by benchmark cleanup paths."""
        try:
            self.all_off()
            self._bench_emit_status(status_callback, f"[bench] {context}: ALL_OFF ok")
            return None
        except Exception as exc:
            message = self._format_exception(exc)
            self._socket_last_error = message
            self._bench_emit_status(status_callback, f"[bench] {context}: ALL_OFF failed: {message}")
            self._close_ethernet_socket()
            return message

    def _refresh_quickack(self, ethernet_socket: socket.socket) -> None:
        """Best-effort refresh of TCP_QUICKACK on Linux.

        The Linux TCP stack documents TCP_QUICKACK as a non-permanent switch,
        so re-applying it before short response reads gives a fairer basis for
        latency comparisons when you explicitly want to test it.
        """
        self._tcp_quickack_last_applied = False
        if not (self._tcp_quickack_requested and self._tcp_quickack_supported):
            return
        try:
            ethernet_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            self._tcp_quickack_last_applied = True
        except OSError:
            self._tcp_quickack_apply_errors += 1

    def _apply_socket_latency_options(self, ethernet_socket: socket.socket) -> None:
        """Apply best-effort low-latency socket options to a TCP socket."""
        ethernet_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self._tcp_nodelay:
            ethernet_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        else:
            try:
                ethernet_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
            except OSError:
                pass

        if self._keepalive:
            try:
                ethernet_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except OSError:
                pass

        self._refresh_quickack(ethernet_socket)

    def _open_ethernet_socket(self) -> socket.socket:
        """Open a new TCP socket to the firmware's Ethernet server.

        This does **not** reuse or modify the persistent socket stored on the
        instance. Use `_connect_ethernet_socket(reuse=True)` if you want
        connection reuse.
        """
        if not self._ethernet_ip_address:
            raise RuntimeError(
                "Ethernet mode not set. Call set_ethernet_mode(ip) or pass --ethernet IP."
            )

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._apply_socket_latency_options(s)
        s.settimeout(self._socket_timeout_s)
        s.connect((self._ethernet_ip_address, ETHERNET_SERVER_PORT))
        self._refresh_quickack(s)
        return s

    def _connect_ethernet_socket(self, repeat_count: int = 10, reuse: bool = True) -> socket.socket:
        """Connect (or reuse) a TCP socket to the firmware's Ethernet server."""
        if reuse and (self._ethernet_socket is not None):
            return self._ethernet_socket

        # Only close the stored persistent socket when we're about to replace it.
        if reuse:
            self._close_ethernet_socket()

        last_exc: Exception | None = None
        for _ in range(int(repeat_count)):
            s: socket.socket | None = None
            try:
                s = self._open_ethernet_socket()
                if reuse:
                    self._ethernet_socket = s
                return s
            except (ConnectionRefusedError, TimeoutError, OSError) as e:
                last_exc = e
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass
                # Short backoff; firmware may still be booting.
                time.sleep(0.2)

        raise last_exc if last_exc is not None else ConnectionRefusedError()


    def _recv_exact(self, ethernet_socket: socket.socket, n: int) -> bytes:
        """Receive exactly n bytes from a TCP socket or raise on EOF."""
        data = b""
        while len(data) < n:
            self._refresh_quickack(ethernet_socket)
            chunk = ethernet_socket.recv(n - len(data))
            if not chunk:
                raise ConnectionError("socket closed while receiving")
            data += chunk
        return data

    def _read(self, transport, n: int) -> bytes:
        """Read exactly n bytes from a serial or Ethernet transport."""
        if transport is None:
            raise RuntimeError("No transport provided")
        if isinstance(transport, socket.socket):
            return self._recv_exact(transport, n)
        # Assume pyserial-like.
        data = transport.read(n)
        if data is None:
            return b""
        if len(data) != n:
            raise TimeoutError(f"serial read short: expected {n}, got {len(data)}")
        return data
    def _send_and_receive(self, cmd, ethernet_socket=None, *, return_timings: bool = False):
        """Send a command and wait for a binary response.

        If no socket is provided and we're in Ethernet mode, this reuses a
        persistent TCP connection to avoid per-command connect overhead.

        Parameters
        ----------
        return_timings:
            If True, return a tuple: (payload_bytes, send_ms, recv_ms), where
            send_ms is time spent in send/write calls and recv_ms is time spent
            waiting for and reading the response bytes.
        """
        if self._serial:
            t0 = time.perf_counter_ns()
            if isinstance(cmd, str):
                self._serial.write(cmd.encode())
            else:
                self._serial.write(cmd)
            t1 = time.perf_counter_ns()
            resp_len = self._serial.read(1)
            if not resp_len:
                raise TimeoutError("serial response length timed out")
            response = resp_len + self._serial.read(int(resp_len[0]))
            t2 = time.perf_counter_ns()
            payload = response[3:]
            if return_timings:
                return payload, (t1 - t0) / 1e6, (t2 - t1) / 1e6
            return payload

        # Ethernet
        sock = ethernet_socket if (ethernet_socket is not None) else self._connect_ethernet_socket(reuse=True)

        def _do_io(s: socket.socket):
            t0 = time.perf_counter_ns()
            if isinstance(cmd, str):
                s.sendall(cmd.encode())
            else:
                s.sendall(cmd)
            t1 = time.perf_counter_ns()

            resp_len = self._recv_exact(s, 1)
            payload = self._recv_exact(s, int(resp_len[0]))
            t2 = time.perf_counter_ns()

            out = (resp_len + payload)[3:]
            if return_timings:
                return out, (t1 - t0) / 1e6, (t2 - t1) / 1e6
            return out

        # If we're using the persistent socket, allow one reconnect attempt.
        attempts = 1 if (ethernet_socket is not None) else 2
        for _ in range(attempts):
            try:
                return _do_io(sock)
            except (OSError, ConnectionError) as e:
                if ethernet_socket is not None:
                    raise
                self._socket_reconnects += 1
                self._socket_last_error = repr(e)
                self._debug_print(f"socket error ({e}), reconnecting")
                self._close_ethernet_socket()
                sock = self._connect_ethernet_socket(reuse=True)

        raise ConnectionError("failed to send/receive over Ethernet after reconnect")
    def _send_and_receive_stream(
            self,
            stream_header: bytes,
            frame_chunked: list[bytes],
            ethernet_socket: socket.socket | None = None,
            *,
            return_timings: bool = False,
    ):
        """Send a stream frame (header + payload) and wait for response.

        This mirrors `_send_and_receive()` but supports chunked payload sends.

        Parameters
        ----------
        ethernet_socket:
            Optional explicit socket. If omitted, uses (and can reconnect) the
            instance's persistent Ethernet socket.
        return_timings:
            If True, return (payload_bytes, send_ms, recv_ms).
        """
        sock = ethernet_socket if (ethernet_socket is not None) else self._connect_ethernet_socket(reuse=True)

        def _do_io(s: socket.socket):
            t0 = time.perf_counter_ns()
            s.sendall(stream_header)
            for chunk in frame_chunked:
                s.sendall(chunk)
            t1 = time.perf_counter_ns()

            resp_len = self._recv_exact(s, 1)
            payload = self._recv_exact(s, int(resp_len[0]))
            t2 = time.perf_counter_ns()

            out = (resp_len + payload)[3:]
            if return_timings:
                return out, (t1 - t0) / 1e6, (t2 - t1) / 1e6
            return out

        # If we're using the persistent socket, allow one reconnect attempt.
        attempts = 1 if (ethernet_socket is not None) else 2
        for _ in range(attempts):
            try:
                return _do_io(sock)
            except (OSError, ConnectionError) as e:
                if ethernet_socket is not None:
                    raise
                self._socket_reconnects += 1
                self._socket_last_error = repr(e)
                self._debug_print(f"socket error ({e}), reconnecting")
                self._close_ethernet_socket()
                sock = self._connect_ethernet_socket(reuse=True)

        raise ConnectionError("failed to send/receive STREAM_FRAME over Ethernet after reconnect")

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
        if serial is None:
            raise RuntimeError(
                "Serial transport requires pyserial. Install runtime dependencies or `pip install pyserial`."
            )

        self._close_ethernet_socket()
        self._ethernet_ip_address = ''
        if self._serial:
            self._serial.close()

        self._serial = serial.Serial()
        self._serial.port = port
        self._serial.baudrate = baudrate
        self._serial.timeout = self._serial_timeout_s
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

    def show_pattern_frame(
            self,
            pattern_id,
            frame_index,
            frame_rate: int = 0,
            runtime_duration: int = 0,
            gain: int = 0x10,
            ethernet_socket=None,
    ):
        """Show pattern frame.

        Parameters
        ----------
        pattern_id:
            Pattern ID on the controller.
        frame_index:
            Initial frame index.
        frame_rate:
            Target refresh rate (Hz). Some firmware builds use this as the mode
            target_hz for perf sessions.
        runtime_duration:
            Duration in 100ms ticks (same unit as play_pattern TRIAL_PARAMS).
            Use 0 for "run until interrupted".
        """
        control_mode = 0x03
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
        self.show_pattern_frame(pattern_id, frame_index_min, ethernet_socket=ethernet_socket)
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

    def get_perf_stats(self, ethernet_socket=None) -> bytes:
        """Fetch a raw performance stats snapshot (binary payload)."""
        return self._send_and_receive(b'\x01\x71', ethernet_socket)

    def reset_perf_stats(self, ethernet_socket=None):
        """Reset performance counters on the device."""
        self._send_and_receive(b'\x01\x72', ethernet_socket)

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
            collect_timings: bool = False,
            status_callback: StatusCallback | None = None,
            stop_after: bool = True,
    ):
        """Stream a `.pattern` file's frames at a fixed rate for a fixed duration.

        Notes
        -----
        - `runtime_duration` uses the same unit as TRIAL_PARAMS: **100ms ticks**.
          For example, `runtime_duration=50` streams for ~5 seconds.
        - `pattern_path` may be either:
            - a `.pattern` file: [uint32_le frame_size][frame0 bytes][frame1 bytes]...
            - a `.pat` file: [<HHBBB header (7 bytes)>][frame bytes...]

        Returns
        -------
        dict
            Basic host-side throughput stats.
        """
                # Read frames from either:
        #   1) ".pattern" format: [uint32_le frame_size][frame0 bytes][frame1 bytes]...
        #   2) ".pat" format (as in ./patterns/*.pat): [<HHBBB header (7 bytes)>][frame bytes...]
        #
        # The STREAM_FRAME command only supports uint16 payload lengths, so very
        # large frames (>65535 bytes) are not supported.
        with open(pattern_path, "rb") as f:
            file_bytes = f.read()

        file_size = len(file_bytes)
        frames: list[bytes] = []
        num_frames = 0

        # Try ".pattern"
        if file_size >= 4:
            frame_size = struct.unpack("<I", file_bytes[:4])[0]
            if 0 < frame_size <= 65535 and (file_size - 4) > 0 and ((file_size - 4) % frame_size == 0):
                num_frames = int((file_size - 4) / frame_size)
                frames = [
                    file_bytes[4 + (i * frame_size): 4 + ((i + 1) * frame_size)]
                    for i in range(num_frames)
                ]

        # Fall back to ".pat"
        if not frames:
            if file_size < PATTERN_HEADER_SIZE:
                raise ValueError(f"{pattern_path} is too small to be a .pattern or .pat file")
            header = struct.unpack("<HHBBB", file_bytes[:PATTERN_HEADER_SIZE])
            frame_count = int(header[0]) * int(header[1])
            if frame_count <= 0:
                raise ValueError(f"invalid .pat header frame_count={frame_count} in {pattern_path}")

            blob = file_bytes[PATTERN_HEADER_SIZE:]
            if len(blob) % frame_count != 0:
                raise ValueError(
                    f".pat size {file_size} not compatible with frame_count {frame_count} in {pattern_path}"
                )

            frame_size = int(len(blob) / frame_count)
            if frame_size > 65535:
                raise ValueError(
                    f".pat frame_size {frame_size} exceeds STREAM_FRAME uint16 limit in {pattern_path}"
                )

            num_frames = int(frame_count)
            frames = [blob[i * frame_size:(i + 1) * frame_size] for i in range(num_frames)]

        runtime_duration_s = float(runtime_duration) / float(RUNTIME_DURATION_PER_SECOND)
        frames_target = int(runtime_duration_s * float(frame_rate)) if frame_rate else 0
        frame_period_ns = int((1.0 / float(frame_rate)) * 1e9) if frame_rate else 0

        analog_update_period_ns = int((1.0 / float(analog_update_rate)) * 1e9) if analog_update_rate else 0

        # Map waveform output [-1..1] into a conservative 12-bit-ish range.
        analog_amplitude = (ANALOG_OUTPUT_VALUE_MAX - ANALOG_OUTPUT_VALUE_MIN) / 2.0
        analog_offset = (ANALOG_OUTPUT_VALUE_MAX + ANALOG_OUTPUT_VALUE_MIN) / 2.0

        def analog_waveform_for(name: str):
            if name == 'sin':
                return math.sin
            if name == 'square':
                return lambda x: 1.0 if math.sin(x) >= 0 else -1.0
            if name == 'sawtooth':
                return lambda x: 2.0 * (x / (2.0 * math.pi) - math.floor(0.5 + x / (2.0 * math.pi)))
            if name == 'triangle':
                return lambda x: 2.0 * abs(2.0 * (x / (2.0 * math.pi) - math.floor(0.5 + x / (2.0 * math.pi)))) - 1.0
            if name == 'constant':
                return lambda x: 0.0
            raise ValueError(f'Invalid analog output waveform: {name}')

        # Ensure persistent socket is established once for the run.
        self._connect_ethernet_socket(reuse=True)

        bytes_sent = 0
        frames_streamed = 0

        send_ms_samples: list[float] = []
        resp_wait_ms_samples: list[float] = []
        cmd_rtt_ms_samples: list[float] = []

        wf = analog_waveform_for(str(analog_out_waveform))
        last_analog_update_ns = 0
        analog_value_cached = int(round(analog_offset))

        start_time_ns = time.perf_counter_ns()
        end_time_ns = start_time_ns + int(runtime_duration_s * 1e9)

        # Schedule the first frame "immediately" and then advance by period.
        next_frame_deadline_ns = start_time_ns

        next_progress_ns = None
        if progress_interval_s and (progress_interval_s > 0):
            next_progress_ns = start_time_ns + int(progress_interval_s * 1e9)

        i = 0
        while True:
            now_ns = time.perf_counter_ns()
            if now_ns >= end_time_ns:
                break

            # Rate limiting: hybrid sleep + spin. This keeps CPU load reasonable,
            # but still gives predictable timing at ~200Hz+.
            if frame_period_ns:
                while True:
                    now_ns = time.perf_counter_ns()
                    remaining_ns = next_frame_deadline_ns - now_ns
                    if remaining_ns <= 0:
                        break
                    if remaining_ns > 2_000_000:  # > 2ms
                        time.sleep((remaining_ns - 1_000_000) / 1e9)  # leave ~1ms for spin
                    else:
                        pass

                # If we crossed the end-of-window while waiting, stop without
                # starting another frame.
                if time.perf_counter_ns() >= end_time_ns:
                    break

            frame_index = i % num_frames
            frame = frames[frame_index]

            # Analog output update (optional)
            now_ns = time.perf_counter_ns()
            if analog_update_period_ns and (now_ns - last_analog_update_ns) >= analog_update_period_ns:
                t_s = (now_ns - start_time_ns) / 1e9
                analog_phase = (t_s * float(analog_frequency)) * (2.0 * math.pi)
                analog_output_value_f = analog_amplitude * float(wf(analog_phase)) + analog_offset
                analog_value_cached = int(
                    max(
                        ANALOG_OUTPUT_VALUE_MIN,
                        min(ANALOG_OUTPUT_VALUE_MAX, round(analog_output_value_f)),
                    )
                )
                last_analog_update_ns = now_ns

            analog_output_value = int(analog_value_cached)

            # Stream frame header: cmd(0x32), data_len(uint16), analog(uint16), reserved(uint16)
            data_len = len(frame)
            stream_header = struct.pack('<BHHH', 0x32, data_len, analog_output_value, 0)

            if stream_cmd_coalesced:
                if collect_timings:
                    _, send_ms, recv_ms = self._send_and_receive(stream_header + frame, return_timings=True)
                    send_ms_samples.append(float(send_ms))
                    resp_wait_ms_samples.append(float(recv_ms))
                    cmd_rtt_ms_samples.append(float(send_ms) + float(recv_ms))
                else:
                    self._send_and_receive(stream_header + frame)
            else:
                # Chunk the frame payload for better control over send sizes.
                frame_chunked = [frame[i:i + CHUNK_SIZE] for i in range(0, len(frame), CHUNK_SIZE)]
                if collect_timings:
                    _, send_ms, recv_ms = self._send_and_receive_stream(
                        stream_header,
                        frame_chunked,
                        return_timings=True,
                    )
                    send_ms_samples.append(float(send_ms))
                    resp_wait_ms_samples.append(float(recv_ms))
                    cmd_rtt_ms_samples.append(float(send_ms) + float(recv_ms))
                else:
                    self._send_and_receive_stream(stream_header, frame_chunked)

            frames_streamed += 1
            bytes_sent += (len(stream_header) + data_len)

            # Progress (throttled)
            if next_progress_ns is not None:
                now_ns = time.perf_counter_ns()
                if now_ns >= next_progress_ns:
                    elapsed_s = (now_ns - start_time_ns) / 1e9
                    rate_hz = frames_streamed / elapsed_s if elapsed_s > 0 else 0.0
                    if frames_target:
                        self._bench_emit_status(status_callback, f'[bench] stream_frames: {frames_streamed}/{frames_target} frames ({rate_hz:.1f} Hz)')
                    else:
                        self._bench_emit_status(status_callback, f'[bench] stream_frames: {frames_streamed} frames ({rate_hz:.1f} Hz)')
                    next_progress_ns += int(progress_interval_s * 1e9)

            if frame_period_ns:
                next_frame_deadline_ns += frame_period_ns
            i += 1
        if stop_after:
            self._send_and_receive(bytes([1, 0]))

        elapsed_s = (time.perf_counter_ns() - start_time_ns) / 1e9
        rate_hz = frames_streamed / elapsed_s if elapsed_s > 0 else 0.0
        mbps = (bytes_sent * 8) / (elapsed_s * 1e6) if elapsed_s > 0 else 0.0
        self._bench_emit_status(status_callback, f'[bench] stream_frames: frames={frames_streamed} elapsed_s={elapsed_s:.3f} rate={rate_hz:.1f} Hz tx={mbps:.2f} Mb/s')

        result = {
            "frames": frames_streamed,
            "elapsed_s": elapsed_s,
            "rate_hz": rate_hz,
            "bytes_sent": bytes_sent,
            "tx_mbps": mbps,
            "duration_requested_s": runtime_duration_s,
            "frames_target": frames_target,
            "frame_bytes": int(frame_size),
            "stream_header_bytes": 7,
            "bytes_per_frame": int(frame_size) + 7,
        }

        if collect_timings and cmd_rtt_ms_samples:
            result["cmd_rtt_ms"] = self._bench_summarize_ms(cmd_rtt_ms_samples)
            result["send_ms"] = self._bench_summarize_ms(send_ms_samples)
            result["response_wait_ms"] = self._bench_summarize_ms(resp_wait_ms_samples)

        return result

    def all_off_str(self):
        """Turn all panels off with string."""
        self._send_and_receive('ALL_OFF')

    def all_on_str(self):
        """Turn all panels on with string."""
        self._send_and_receive('ALL_ON')

    # ---------------------------------------------------------------------
    # Benchmark helpers (host-side)
    # ---------------------------------------------------------------------

    def get_socket_reconnects(self, reset: bool = False) -> int:
        """Return the number of automatic Ethernet reconnects seen so far.

        Notes
        -----
        - This counter only increments when `_send_and_receive()` is using the
          instance's persistent Ethernet socket (i.e. you did not pass an explicit
          `ethernet_socket=` argument).
        """
        n = int(self._socket_reconnects)
        if reset:
            self._socket_reconnects = 0
        return n

    @staticmethod
    def _bench_percentile(sorted_values: list[float], pct: float) -> float:
        """Nearest-rank percentile on a *sorted* list."""
        if not sorted_values:
            return float("nan")
        if pct <= 0:
            return float(sorted_values[0])
        if pct >= 100:
            return float(sorted_values[-1])
        idx = int((pct / 100.0) * (len(sorted_values) - 1))
        return float(sorted_values[idx])

    @classmethod
    def _bench_summarize_ms(cls, samples_ms: list[float]) -> dict:
        """Summarize a list of millisecond samples."""
        values = sorted(float(x) for x in samples_ms)
        if not values:
            return {
                "samples": 0,
                "mean_ms": float("nan"),
                "min_ms": float("nan"),
                "p50_ms": float("nan"),
                "p95_ms": float("nan"),
                "p99_ms": float("nan"),
                "max_ms": float("nan"),
            }
        return {
            "samples": int(len(values)),
            "mean_ms": float(statistics.mean(values)),
            "min_ms": float(values[0]),
            "p50_ms": cls._bench_percentile(values, 50),
            "p95_ms": cls._bench_percentile(values, 95),
            "p99_ms": cls._bench_percentile(values, 99),
            "max_ms": float(values[-1]),
        }

    def _bench_progress_maybe(
        self,
        *,
        status_callback: StatusCallback | None,
        phase: str,
        completed: int,
        total: int | None,
        started_ns: int,
        next_progress_ns: int | None,
        progress_interval_s: float,
    ) -> int | None:
        """Emit throttled benchmark progress and return the next deadline."""
        if next_progress_ns is None:
            return None

        now_ns = time.perf_counter_ns()
        if now_ns < next_progress_ns:
            return next_progress_ns

        elapsed_s = (now_ns - started_ns) / 1e9
        rate = (completed / elapsed_s) if elapsed_s > 0 else 0.0
        if total is None:
            detail = f"{completed} completed"
        else:
            detail = f"{completed}/{total} completed"
        self._bench_emit_status(status_callback, f"[bench] {phase}: {detail} ({rate:.1f}/s)")

        step_ns = max(1, int(float(progress_interval_s) * 1e9))
        while next_progress_ns <= now_ns:
            next_progress_ns += step_ns
        return next_progress_ns

    def bench_metadata(self, label: str | None = None) -> dict:
        """Return a small metadata blob to attach to benchmark results."""
        try:
            from .__about__ import __version__ as pkg_version  # type: ignore
        except Exception:
            pkg_version = None

        meta = {
            "label": label,
            "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "package_version": pkg_version,
            "transport": "serial" if (self._serial is not None) else "ethernet",
            "ethernet_ip": self._ethernet_ip_address if self._ethernet_ip_address else None,
            "serial_port": getattr(self._serial, "port", None) if self._serial is not None else None,
            "tcp_nodelay": self._tcp_nodelay,
            "tcp_quickack_requested": self._tcp_quickack_requested,
            "tcp_quickack_supported": self._tcp_quickack_supported,
            "tcp_quickack_last_applied": self._tcp_quickack_last_applied,
            "tcp_quickack_apply_errors": self._tcp_quickack_apply_errors,
            "socket_keepalive": self._keepalive,
            "socket_timeout_s": self._socket_timeout_s,
            "serial_timeout_s": self._serial_timeout_s,
        }

        # Best-effort socket endpoint capture (only if a persistent socket exists).
        if self._ethernet_socket is not None:
            try:
                local = self._ethernet_socket.getsockname()
                peer = self._ethernet_socket.getpeername()
                meta["ethernet_local"] = {"ip": local[0], "port": local[1]}
                meta["ethernet_peer"] = {"ip": peer[0], "port": peer[1]}
            except OSError:
                pass

        # Best-effort interface / route metadata (useful when comparing switches/NICs).
        peer_ip = meta.get("ethernet_ip")
        if peer_ip:
            try:
                route_out = subprocess.check_output(["ip", "route", "get", str(peer_ip)], text=True).strip()
                meta["net_route_get"] = route_out
                m = re.search(r"\bdev\s+(\S+)", route_out)
                iface = m.group(1) if m else None
                if iface:
                    info: dict[str, object] = {"interface": iface}
                    sysfs_base = f"/sys/class/net/{iface}"

                    def _read_sysfs(name: str) -> str | None:
                        try:
                            with open(f"{sysfs_base}/{name}", "r", encoding="utf-8") as f:
                                return f.read().strip()
                        except Exception:
                            return None

                    mtu = _read_sysfs("mtu")
                    if mtu is not None:
                        try:
                            info["mtu"] = int(mtu)
                        except ValueError:
                            info["mtu"] = mtu

                    speed = _read_sysfs("speed")
                    if speed is not None:
                        try:
                            info["speed_mbps"] = int(speed)
                        except ValueError:
                            info["speed_mbps"] = speed

                    duplex = _read_sysfs("duplex")
                    if duplex is not None:
                        info["duplex"] = duplex

                    operstate = _read_sysfs("operstate")
                    if operstate is not None:
                        info["operstate"] = operstate

                    mac = _read_sysfs("address")
                    if mac is not None:
                        info["mac"] = mac

                    meta["net_interface"] = info
            except Exception:
                # Non-Linux hosts (or minimal containers) may not have `ip` or sysfs.
                pass


        return meta

    def bench_connect_time(self, iters: int = 200) -> dict:
        """Measure TCP connect() time to the controller (Ethernet only)."""
        if not self._ethernet_ip_address:
            raise RuntimeError("bench_connect_time requires Ethernet mode (set_ethernet_mode).")

        # Clear any prior socket error so results are per-run.
        self._socket_last_error = None

        samples_ms: list[float] = []
        errors = 0

        for _ in range(int(iters)):
            s: socket.socket | None = None
            t0 = time.perf_counter_ns()
            try:
                s = self._open_ethernet_socket()
                t1 = time.perf_counter_ns()
                samples_ms.append((t1 - t0) / 1e6)
            except Exception:
                errors += 1
            finally:
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass

        summary = self._bench_summarize_ms(samples_ms)
        summary.update({"iters": int(iters), "errors": int(errors)})
        return summary

    def bench_command_rtt(
            self,
            iters: int = 2000,
            wrap_mode: bool = True,
            connect_mode: str = "persistent",
            warmup: int = 20,
            progress_interval_s: float = 1.0,
            status_callback: StatusCallback | None = None,
    ) -> dict:
        """Measure host-side RTT for a small request/response command.

        This runs repeated `get_perf_stats()` calls and measures the host round-trip
        time. Use this to compare:
        - host computers,
        - Ethernet switches / LANs,
        - firmware Ethernet backends (mongoose vs QNEthernet),
        while keeping the application-level payload constant.

        Parameters
        ----------
        iters:
            Number of samples to record.
        wrap_mode:
            If True, the test is bounded by ALL_ON/ALL_OFF so the firmware-side
            perf probe is active and will emit a PERF_* report at mode end.
        connect_mode:
            "persistent" (default) reuses the controller TCP connection.
            "new_connection" opens/closes a new TCP connection per iteration.
        warmup:
            Number of warmup iterations (not recorded). Useful to get past ARP,
            TCP slow start, or first-command firmware setup.
        """
        if connect_mode not in {"persistent", "new_connection"}:
            raise ValueError("connect_mode must be 'persistent' or 'new_connection'")

        # Clear any prior socket error so results are per-run.
        self._socket_last_error = None

        reconnects_before = self.get_socket_reconnects(reset=False)
        cleanup_error: str | None = None
        progress_step_ns = max(1, int(float(progress_interval_s) * 1e9)) if progress_interval_s > 0 else 0

        try:
            if wrap_mode:
                self.all_on()

            self.reset_perf_stats()

            # Warmup
            for _ in range(int(warmup)):
                if connect_mode == "persistent":
                    self.get_perf_stats()
                else:
                    s = self._open_ethernet_socket()
                    try:
                        self.get_perf_stats(ethernet_socket=s)
                    finally:
                        s.close()

            rtts_ms: list[float] = []
            bytes_tx = 0
            bytes_rx = 0
            errors = 0
            measure_start_ns = time.perf_counter_ns()
            next_progress_ns = (
                measure_start_ns + progress_step_ns if progress_step_ns > 0 else None
            )

            for iteration in range(int(iters)):
                if connect_mode == "persistent":
                    t0 = time.perf_counter_ns()
                    payload = self.get_perf_stats()
                    t1 = time.perf_counter_ns()
                    rtts_ms.append((t1 - t0) / 1e6)
                    bytes_tx += 2  # b'q'
                    bytes_rx += (len(payload) + 3)  # status + echo + payload (length excluded)
                else:
                    s = self._open_ethernet_socket()
                    try:
                        t0 = time.perf_counter_ns()
                        payload = self.get_perf_stats(ethernet_socket=s)
                        t1 = time.perf_counter_ns()
                        rtts_ms.append((t1 - t0) / 1e6)
                        bytes_tx += 2
                        bytes_rx += (len(payload) + 3)
                    except Exception:
                        errors += 1
                    finally:
                        try:
                            s.close()
                        except Exception:
                            pass

                next_progress_ns = self._bench_progress_maybe(
                    status_callback=status_callback,
                    phase="command_rtt",
                    completed=iteration + 1,
                    total=int(iters),
                    started_ns=measure_start_ns,
                    next_progress_ns=next_progress_ns,
                    progress_interval_s=float(progress_interval_s),
                )

            summary = self._bench_summarize_ms(rtts_ms)
            reconnects_after = self.get_socket_reconnects(reset=False)

            summary.update(
                {
                    "iters": int(iters),
                    "warmup": int(warmup),
                    "connect_mode": connect_mode,
                    "bytes_tx": int(bytes_tx),
                    "bytes_rx": int(bytes_rx),
                    "errors": int(errors),
                    "reconnects": int(reconnects_after - reconnects_before),
                    "last_socket_error": self._socket_last_error,
                }
            )
        finally:
            if wrap_mode:
                cleanup_error = self._safe_all_off(
                    status_callback=status_callback,
                    context="command_rtt cleanup",
                )

        if cleanup_error is not None:
            raise RuntimeError(f"command_rtt cleanup failed: {cleanup_error}")

        return summary

    def bench_spf_updates(
            self,
            rate_hz: float = 200.0,
            seconds: float = 5.0,
            pattern_id: int = 10,
            frame_min: int = 0,
            frame_max: int = 1000,
            pacing: str = "target",
            warmup: int = 0,
            progress_interval_s: float = 1.0,
            status_callback: StatusCallback | None = None,
    ) -> dict:
        """Benchmark SHOW_PATTERN_FRAME update performance (SPF).

        This measures host-side performance of repeated `SET_FRAME_POSITION_CMD`
        requests and is intended to be paired with QS capture so you can compare
        firmware-side `PERF_UPD kind=SPF` and `PERF_NET` across:
        - firmware Ethernet stacks,
        - switches / host NICs / LANs.

        Parameters
        ----------
        pacing:
            "target" attempts to pace updates to `rate_hz`.
            "max" sends updates as fast as possible (no pacing).
        warmup:
            Number of warmup updates to send before starting measurement.
        """
        if pacing not in {"target", "max"}:
            raise ValueError("pacing must be 'target' or 'max'")

        # Clear any prior socket error so results are per-run.
        self._socket_last_error = None

        reconnects_before = self.get_socket_reconnects(reset=False)
        cleanup_error: str | None = None
        progress_step_ns = max(1, int(float(progress_interval_s) * 1e9)) if progress_interval_s > 0 else 0

        try:
            self.reset_perf_stats()

            # Some firmware builds use TRIAL_PARAMS.frame_rate as target_hz.
            self.show_pattern_frame(int(pattern_id), int(frame_min), frame_rate=int(rate_hz))

            # Warmup updates (not recorded)
            frame = int(frame_min)
            for _ in range(int(warmup)):
                self.update_pattern_frame(frame)
                frame += 1
                if frame > int(frame_max):
                    frame = int(frame_min)

            start_ns = time.perf_counter_ns()
            end_ns = start_ns + int(float(seconds) * 1e9)

            period_ns = int(1e9 / float(rate_hz)) if (rate_hz and rate_hz > 0) else 0
            next_deadline_ns = start_ns + period_ns if period_ns else 0

            updates = 0
            update_rtts_ms: list[float] = []
            update_starts_ns: list[int] = []
            late_starts = 0
            max_start_lag_ns = 0

            bytes_tx = 0
            bytes_rx = 0
            next_progress_ns = start_ns + progress_step_ns if progress_step_ns > 0 else None

            while time.perf_counter_ns() < end_ns:
                now_ns = time.perf_counter_ns()
                if period_ns and pacing == "target":
                    # Lag relative to ideal schedule
                    sched_start_ns = start_ns + (updates * period_ns)
                    lag_ns = now_ns - sched_start_ns
                    if lag_ns > 0:
                        late_starts += 1
                        if lag_ns > max_start_lag_ns:
                            max_start_lag_ns = lag_ns

                update_starts_ns.append(now_ns)

                t0 = time.perf_counter_ns()
                self.update_pattern_frame(frame)
                t1 = time.perf_counter_ns()
                update_rtts_ms.append((t1 - t0) / 1e6)

                # update_pattern_frame command is 4 bytes, response is typically 3 bytes (no payload)
                bytes_tx += 4
                bytes_rx += 3

                updates += 1
                frame += 1
                if frame > int(frame_max):
                    frame = int(frame_min)

                next_progress_ns = self._bench_progress_maybe(
                    status_callback=status_callback,
                    phase="spf_updates",
                    completed=updates,
                    total=None,
                    started_ns=start_ns,
                    next_progress_ns=next_progress_ns,
                    progress_interval_s=float(progress_interval_s),
                )

                if period_ns and pacing == "target":
                    # Hybrid sleep + spin to reduce CPU load while keeping decent timing.
                    while True:
                        now_ns = time.perf_counter_ns()
                        remaining_ns = next_deadline_ns - now_ns
                        if remaining_ns <= 0:
                            break
                        if remaining_ns > 2_000_000:  # > 2ms
                            time.sleep((remaining_ns - 1_000_000) / 1e9)  # leave ~1ms for spin
                        else:
                            pass
                    next_deadline_ns += period_ns

            elapsed_s = (time.perf_counter_ns() - start_ns) / 1e9
            achieved_hz = updates / elapsed_s if elapsed_s > 0 else 0.0

            # Host-side IFI (time between update call starts)
            ifi_ms: list[float] = []
            for i in range(1, len(update_starts_ns)):
                ifi_ms.append((update_starts_ns[i] - update_starts_ns[i - 1]) / 1e6)

            summary = {
                "updates": int(updates),
                "elapsed_s": float(elapsed_s),
                "target_hz": float(rate_hz),
                "achieved_hz": float(achieved_hz),
                "pacing": pacing,
                "warmup": int(warmup),
                "update_rtt_ms": self._bench_summarize_ms(update_rtts_ms),
                "host_ifi_ms": self._bench_summarize_ms(ifi_ms),
                "late_starts": int(late_starts),
                "max_start_lag_ms": float(max_start_lag_ns / 1e6),
                "bytes_tx": int(bytes_tx),
                "bytes_rx": int(bytes_rx),
                "reconnects": int(self.get_socket_reconnects(reset=False) - reconnects_before),
                "last_socket_error": self._socket_last_error,
            }
        finally:
            cleanup_error = self._safe_all_off(
                status_callback=status_callback,
                context="spf_updates cleanup",
            )

        if cleanup_error is not None:
            raise RuntimeError(f"spf_updates cleanup failed: {cleanup_error}")

        return summary

    def bench_stream_frames(
            self,
            pattern_path: str,
            frame_rate: float = 200.0,
            seconds: float = 5.0,
            stream_cmd_coalesced: bool = True,
            progress_interval_s: float = 1.0,
            analog_out_waveform: str = "constant",
            analog_update_rate: float = 1.0,
            analog_frequency: float = 0.0,
            collect_timings: bool = True,
            status_callback: StatusCallback | None = None,
    ) -> dict:
        """Benchmark STREAM_FRAME throughput using `stream_frames()`.

        Notes
        -----
        - `seconds` is converted into the library's TRIAL_PARAMS runtime_duration
          unit (100ms ticks).
        - `pattern_path` can be either a `.pattern` file (frame_size header) or
          a `.pat` file from the `patterns/` directory.
        """
        # Clear any prior socket error so results are per-run.
        self._socket_last_error = None

        reconnects_before = self.get_socket_reconnects(reset=False)
        cleanup_error: str | None = None

        try:
            self.reset_perf_stats()

            runtime_duration = int(round(float(seconds) * float(RUNTIME_DURATION_PER_SECOND)))
            stats = self.stream_frames(
                str(pattern_path),
                float(frame_rate),
                runtime_duration,
                str(analog_out_waveform),
                float(analog_update_rate),
                float(analog_frequency),
                stream_cmd_coalesced=bool(stream_cmd_coalesced),
                progress_interval_s=float(progress_interval_s),
                collect_timings=bool(collect_timings),
                status_callback=status_callback,
                stop_after=False,
            )
            stats.update(
                {
                    "pattern_path": str(pattern_path),
                    "frame_rate": float(frame_rate),
                    "seconds": float(seconds),
                    "stream_cmd_coalesced": bool(stream_cmd_coalesced),
                    "reconnects": int(self.get_socket_reconnects(reset=False) - reconnects_before),
                    "last_socket_error": self._socket_last_error,
                }
            )
        finally:
            cleanup_error = self._safe_all_off(
                status_callback=status_callback,
                context="stream_frames cleanup",
            )

        if cleanup_error is not None:
            raise RuntimeError(f"stream_frames cleanup failed: {cleanup_error}")

        return stats

    def bench_suite(
            self,
            label: str | None = None,
            *,
            include_connect: bool = False,
            connect_iters: int = 200,
            cmd_iters: int = 2000,
            cmd_connect_mode: str = "persistent",
            spf_rate: float = 200.0,
            spf_seconds: float = 5.0,
            spf_pattern_id: int = 10,
            spf_frame_min: int = 0,
            spf_frame_max: int = 1000,
            spf_pacing: str = "target",
            stream_path: str | None = None,
            stream_rate: float = 200.0,
            stream_seconds: float = 5.0,
            stream_coalesced: bool = True,
            progress_interval_s: float = 1.0,
            bench_io_timeout_s: float | None = BENCH_IO_TIMEOUT_S,
            status_callback: StatusCallback | None = None,
    ) -> dict:
        """Run a repeatable benchmark suite and return structured results.

        This is useful for collecting comparable measurements across:
        - firmware builds,
        - Ethernet stacks (mongoose / QNEthernet),
        - switches / cables / VLANs,
        - host computers.

        Tip: attach a `label` like "lab-switch-A / laptop-1" and save results
        to a JSONL file with `write_bench_jsonl()`.
        """
        results: dict = {
            "meta": self.bench_metadata(label=label),
            "status": "ok",
            "failed_phase": None,
            "error": None,
            "phases": [],
        }
        results["meta"]["bench_io_timeout_s"] = self._coerce_timeout(bench_io_timeout_s)

        def run_phase(name: str, fn, /, **kwargs) -> bool:
            phase = {
                "name": name,
                "status": "running",
                "started_utc": self._utc_now_iso(),
            }
            results["phases"].append(phase)
            self._bench_emit_status(status_callback, f"[bench] starting {name}")
            started_ns = time.perf_counter_ns()
            try:
                results[name] = fn(**kwargs)
            except Exception as exc:
                phase["status"] = "error"
                phase["ended_utc"] = self._utc_now_iso()
                phase["elapsed_s"] = (time.perf_counter_ns() - started_ns) / 1e9
                phase["error_type"] = type(exc).__name__
                phase["error"] = str(exc)
                results["status"] = "error"
                results["failed_phase"] = name
                results["error"] = {
                    "phase": name,
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                self._bench_emit_status(
                    status_callback,
                    f"[bench] FAILED {name}: {self._format_exception(exc)}",
                )
                cleanup_error = self._safe_all_off(
                    status_callback=status_callback,
                    context=f"{name} post-error cleanup",
                )
                if cleanup_error is not None:
                    results["cleanup"] = {
                        "all_off_attempted": True,
                        "all_off_ok": False,
                        "all_off_error": cleanup_error,
                    }
                else:
                    results["cleanup"] = {
                        "all_off_attempted": True,
                        "all_off_ok": True,
                        "all_off_error": None,
                    }
                return False

            phase["status"] = "ok"
            phase["ended_utc"] = self._utc_now_iso()
            phase["elapsed_s"] = (time.perf_counter_ns() - started_ns) / 1e9
            self._bench_emit_status(
                status_callback,
                f"[bench] finished {name} in {phase['elapsed_s']:.3f} s",
            )
            return True

        with self.temporary_transport_timeouts(
            socket_timeout_s=bench_io_timeout_s,
            serial_timeout_s=bench_io_timeout_s,
        ):
            if include_connect and not run_phase(
                "connect_time",
                self.bench_connect_time,
                iters=int(connect_iters),
            ):
                return self._bench_finalize_suite_results(results)

            if not run_phase(
                "command_rtt",
                self.bench_command_rtt,
                iters=int(cmd_iters),
                wrap_mode=True,
                connect_mode=str(cmd_connect_mode),
                progress_interval_s=float(progress_interval_s),
                status_callback=status_callback,
            ):
                return self._bench_finalize_suite_results(results)

            if not run_phase(
                "spf_updates",
                self.bench_spf_updates,
                rate_hz=float(spf_rate),
                seconds=float(spf_seconds),
                pattern_id=int(spf_pattern_id),
                frame_min=int(spf_frame_min),
                frame_max=int(spf_frame_max),
                pacing=str(spf_pacing),
                progress_interval_s=float(progress_interval_s),
                status_callback=status_callback,
            ):
                return self._bench_finalize_suite_results(results)

            if stream_path and not run_phase(
                "stream_frames",
                self.bench_stream_frames,
                pattern_path=str(stream_path),
                frame_rate=float(stream_rate),
                seconds=float(stream_seconds),
                stream_cmd_coalesced=bool(stream_coalesced),
                progress_interval_s=float(progress_interval_s),
                status_callback=status_callback,
            ):
                return self._bench_finalize_suite_results(results)

        return self._bench_finalize_suite_results(results)

    def _bench_finalize_suite_results(self, results: dict) -> dict:
        """Attach any late-bound metadata before returning suite results."""
        if self._ethernet_socket is not None:
            try:
                local = self._ethernet_socket.getsockname()
                peer = self._ethernet_socket.getpeername()
                results["meta"]["ethernet_local"] = {"ip": local[0], "port": local[1]}
                results["meta"]["ethernet_peer"] = {"ip": peer[0], "port": peer[1]}
            except OSError:
                pass

        if "cleanup" not in results:
            results["cleanup"] = {
                "all_off_attempted": False,
                "all_off_ok": None,
                "all_off_error": None,
            }

        return results

    @staticmethod
    def write_bench_jsonl(path: str, result: dict) -> None:
        """Append one benchmark result object to a JSONL file."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, sort_keys=True))
            f.write("\n")
