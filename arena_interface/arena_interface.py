"""Python interface to the Reiser lab ArenaController."""
import socket
import struct


PORT = 62222
IP_ADDRESS = '192.168.10.62'
PATTERN_HEADER_SIZE = 7
BYTE_COUNT_PER_PANEL_GRAYSCALE = 132
REPEAT_LIMIT = 4

class ArenaInterface():
    """Python interface to the Reiser lab ArenaController."""
    def __init__(self, debug=True):
        """Initialize a ArenaHost instance."""
        self._debug = debug

    def _debug_print(self, *args):
        """Print if debug is True."""
        if self._debug:
            print(*args)

    def _send_and_receive(self, cmd):
        """Send command and receive response."""
        if len(cmd) < 32:
            self._debug_print('command: ', cmd)
        repeat_count = 0
        while repeat_count < REPEAT_LIMIT:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                self._debug_print(f'to {IP_ADDRESS} port {PORT}')
                s.settimeout(2)
                try:
                    s.connect((IP_ADDRESS, PORT))
                    s.sendall(cmd)
                    response = s.recv(1024)
                    break
                except (TimeoutError, OSError):
                    self._debug_print('socket timed out')
                    response = None
                    repeat_count += 1
        self._debug_print('response: ', response)

    def reset(self):
        """Reset arena."""
        self._send_and_receive(b'\x01\x01')

    def all_off(self):
        """Turn all panels off."""
        self._send_and_receive(b'\x01\x30')

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

    def set_frame_rate(self, frame_rate):
        """Set frame rate in Hz."""
        cmd_bytes = struct.pack('<BBH', 0x03, 0x12, frame_rate)
        self._send_and_receive(cmd_bytes)

    def all_off_str(self):
        """Turn all panels off with string."""
        self._send_and_receive('ALL_OFF')

    def all_on_str(self):
        """Turn all panels on with string."""
        self._send_and_receive('ALL_ON')
