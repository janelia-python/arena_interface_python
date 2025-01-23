"""Python interface to the Reiser lab ArenaController."""
import os
import atexit
import serial
# import socket


class ArenaInterface():
    """Python interface to the Reiser lab ArenaController."""
    # PORT = 62222
    BAUDRATE = 115200
    def __init__(self, sock=None, debug=True):
        """Initialize a ArenaHost instance."""
        self._debug = debug
        # if sock is None:
        #     self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # else:
        #     self._socket = sock
        atexit.register(self._exit)

    def _exit(self):
        pass
        # self._socket.close()

    def _debug_print(self, to_print):
        """Print if debug is True."""
        if self._debug:
            print(to_print)

    def _send(self, msg):
        """Send message."""
        try:
            self._write_data = msg.encode()
        except UnicodeDecodeError:
            self._write_data = msg
        self._bytes_written = self._serial.write(self._write_data)
        # if self._socket:
        #     totalsent = 0
        #     while totalsent < MSGLEN:
        #         sent = self._socket.send(msg[totalsent:])
        #         if sent == 0:
        #             raise RuntimeError("socket connection broken")
        #         totalsent = totalsent + sent

    def connect_serial(self, port=None):
        """Connect to server through serial port."""
        self._serial = serial.Serial()
        self._debug_print('ArenaHost connecting serial port...')
        self._serial.baudrate = self.BAUDRATE
        self._serial.port = '/dev/ttyACM0'
        self._serial.open()
        if self._serial.is_open:
            self._debug_print('ArenaHost connected through serial port')
        else:
            self._debug_print('ArenaHost not connected!')

    def disconnect_serial(self, port=None):
        """Disconnect serial port."""
        self._serial.close()

    # def connect(self, ip_address):
    #     """Connect to server at ip address."""
    #     self._debug_print('ArenaHost connecting...')
    #     self._socket.connect((ip_address, self.PORT))
    #     self._debug_print('ArenaHost connected')

    def list_serial_ports(self):
        """List serial ports."""
        serial_interface_ports = os.listdir('{0}dev'.format(os.path.sep))
        serial_interface_ports = [x for x in serial_interface_ports if 'ttyUSB' in x or 'ttyACM' in x or 'arduino' in x]
        serial_interface_ports = ['{0}dev{0}{1}'.format(os.path.sep, x) for x in serial_interface_ports]
        print(serial_interface_ports)

    def all_on(self):
        """Turn all panels on."""
        self._send('ALL_ON')
        # self._send(b'\x01\xff')

    def all_off(self):
        """Turn all panels off."""
        self._send('ALL_OFF')
        # self._send(b'\x01\x00')

