"""Python interface to the Reiser lab ArenaController."""
import socket
import struct
import time
import serial
import atexit

import cProfile
import pstats


PORT = 62222
IP_ADDRESS = '192.168.10.62'
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

class ArenaInterface():
    """Python interface to the Reiser lab ArenaController."""
    def __init__(self, debug=True):
        """Initialize a ArenaHost instance."""
        self._debug = debug
        self._serial = None
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

    def _connect_ethernet_socket(self):
        """
        Connect and return an ethernet socket if in ethernet mode.
        """
        ethernet_socket = None
        if not self._serial:
            ethernet_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._debug_print(f'to {IP_ADDRESS} port {PORT}')
            ethernet_socket.settimeout(SOCKET_TIMEOUT)
            repeat_count = 0
            while repeat_count < REPEAT_LIMIT:
                try:
                    ethernet_socket.connect((IP_ADDRESS, PORT))
                    break
                except (TimeoutError, OSError):
                    self._debug_print('stream frames ethernet socket timed out')
                    repeat_count += 1
        return ethernet_socket

    def _read(self, ethernet_socket=None, byte_count=1):
        """Read bytes."""
        response = b''
        if ethernet_socket:
            response = ethernet_socket.recv(byte_count)
        elif self._serial:
            response = self._serial.read(size=byte_count)
        return response

    def _send_and_receive(self, cmd, ethernet_socket=None):
        """Send command and receive response."""
        if len(cmd) < 32:
            self._debug_print('command: ', cmd)
        response = None
        repeat_count = 0
        while repeat_count < REPEAT_LIMIT:
            if ethernet_socket:
                try:
                    ethernet_socket.sendall(cmd)
                    response = ethernet_socket.recv(1)
                    if len(response) == 1:
                        response += ethernet_socket.recv(int(response[0]))
                    break
                except (TimeoutError, OSError):
                    self._debug_print('stream frames ethernet socket timed out')
                    repeat_count += 1
            elif self._serial:
                try:
                    bytes_written = self._serial.write(cmd)
                    self._debug_print('bytes_written:', bytes_written)
                    response = self._serial.read(size=1)
                    if len(response) == 1:
                        response += self._serial.read(size=int(response[0]))
                    break
                except serial.SerialTimeoutException:
                    self._debug_print('serial timed out')
                    repeat_count += 1
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    self._debug_print(f'to {IP_ADDRESS} port {PORT}')
                    s.settimeout(SOCKET_TIMEOUT)
                    try:
                        s.connect((IP_ADDRESS, PORT))
                        s.sendall(cmd)
                        response = s.recv(1)
                        if len(response) == 1:
                            response += s.recv(int(response[0]))
                        break
                    except (TimeoutError, OSError):
                        self._debug_print('ethernet socket timed out')
                        repeat_count += 1
        self._debug_print('response: ', response)

    def set_ethernet_mode(self):
        """Set ethernet mode."""
        if self._serial:
            self._serial.close()
        self._serial = None
        return True

    def set_serial_mode(self, port, baudrate=SERIAL_BAUDRATE):
        """Set serial mode specifying the serial port."""
        self._serial = serial.Serial()
        self._serial.port = port
        self._serial.baudrate = baudrate
        self._serial.timeout = SERIAL_TIMEOUT
        self._serial.open()
        return self._serial.is_open

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

    def trial_params(self, pattern_id, frame_rate, runtime_duration):
        """Set trial parameters."""
        control_mode = 0xAA
        init_pos = 0x04
        gain = 0x10
        cmd_bytes = struct.pack('<BBBHhHHH',
                                0x0c,
                                0x08,
                                control_mode,
                                pattern_id,
                                frame_rate,
                                init_pos,
                                gain,
                                runtime_duration)
        runtime_duration_s = (runtime_duration * 1.0) / RUNTIME_DURATION_PER_SECOND
        runtime_duration_ms = int(runtime_duration_s * MILLISECONDS_PER_SECOND)
        self._debug_print('runtime_duration_ms: ', runtime_duration_ms)
        ethernet_socket = self._connect_ethernet_socket()
        self._send_and_receive(cmd_bytes, ethernet_socket)

        while True:
            self._debug_print('waiting for trial end response...')
            time.sleep(1)
            response = self._read(ethernet_socket, 1)
            if len(response) == 1:
                response += self._read(ethernet_socket, int(response[0]))
                break
        self._debug_print('response: ', response)

    def set_refresh_rate(self, refresh_rate):
        """Set refresh rate in Hz."""
        cmd_bytes = struct.pack('<BBH', 0x03, 0x16, refresh_rate)
        self._send_and_receive(cmd_bytes)

    # def stop_display(self):
    #     """Turn all panels off."""
    #     self._send_and_receive(b'\x01\x30')

    def all_on(self):
        """Turn all panels on."""
        self._send_and_receive(b'\x01\xff')

    def stream_frame(self, path, frame_index):
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
            frame_header = struct.pack('<BHHH', 0x32, data_len, 0,  0)
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

    def stream_frames(self, path, frame_rate, runtime_duration):
        """Stream frames in pattern file at some frame rate for some duration."""
        self._debug_print('pattern path: ', path)
        self._debug_print('frame_rate: ', frame_rate)
        if frame_rate != 0:
            frame_period_ns = int(NANOSECONDS_PER_SECOND / frame_rate)
        runtime_duration_ns = int(NANOSECONDS_PER_RUNTIME_DURATION * runtime_duration)
        self._debug_print('frame_period_ns: ', frame_period_ns)
        self._debug_print('runtime_duration_ns: ', runtime_duration_ns)
        frames_displayed_count = 0
        with open(path, mode='rb') as f:
            content = f.read()
            pattern_header = struct.unpack('<HHBBB', content[:PATTERN_HEADER_SIZE])
            self._debug_print('pattern header: ', pattern_header)
            frames = content[PATTERN_HEADER_SIZE:]
            frame_count = pattern_header[0] * pattern_header[1]
            frame_len = len(frames)//frame_count
            self._debug_print('frame_count: ', frame_count)
            frames_to_display_count = int((frame_rate * runtime_duration) / RUNTIME_DURATION_PER_SECOND)
            ethernet_socket = self._connect_ethernet_socket()
            stream_frames_start_time = time.time_ns()
            while frames_displayed_count < frames_to_display_count:
                pattern_start_time = time.time_ns()
                for frame_index in range(0,frame_count):
                    frame_start = frame_index * frame_len
                    # # self._debug_print('frame_start: ', frame_start)
                    frame_end = frame_start + frame_len
                    # # self._debug_print('frame_end: ', frame_end)
                    frame = frames[frame_start:frame_end]
                    data_len = len(frame)
                    # # self._debug_print('data_len: ', data_len)
                    frame_header = struct.pack('<BHHH', 0x32, data_len, 0,  0)
                    # self._debug_print('frame header: ', frame_header)
                    message = frame_header + frame
                    # self._debug_print('len(message): ', len(message))
                    # # self._debug_print('message: ', message)
                    self._send_and_receive(message, ethernet_socket)
                    frames_displayed_count= frames_displayed_count + 1
                    seconds_elapsed = int((time.time_ns() - stream_frames_start_time) / NANOSECONDS_PER_SECOND)
                    print('frames streamed: ', frames_displayed_count, ':', frames_to_display_count, seconds_elapsed)
                    while (time.time_ns() - pattern_start_time) < ((frame_index + 1) * frame_period_ns):
                        pass
            stream_frames_stop_time = time.time_ns()
            duration_s = (stream_frames_stop_time - stream_frames_start_time) / NANOSECONDS_PER_SECOND
            print('stream frames duration:', duration_s)
            frame_rate_actual = frames_displayed_count / duration_s
            print('frame rate requested: ', frame_rate, ', frame rate actual:', frame_rate_actual)
            self.all_off()

    def all_off_str(self):
        """Turn all panels off with string."""
        self._send_and_receive('ALL_OFF')

    def all_on_str(self):
        """Turn all panels on with string."""
        self._send_and_receive('ALL_ON')
