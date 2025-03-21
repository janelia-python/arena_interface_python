"""Python interface to the Reiser lab ArenaController."""
import os
import atexit
import serial
import socket
import nmap3
from serial_interface import SerialInterface, find_serial_interface_ports


PORT = 62222
IP_ADDRESS = '192.168.10.62'
IP_RANGE = '192.168.10.0/24'
SERIAL_BAUDRATE = 115200

def results_filter(pair):
    key, value = pair
    try:
        ports = value['ports']

        for port in ports:
            if port['portid'] == str(PORT) and port['state'] == 'open':
                return True
    except (KeyError, TypeError) as e:
        pass

    return False

class ArenaInterface():
    """Python interface to the Reiser lab ArenaController."""
    def __init__(self, debug=True):
        """Initialize a ArenaHost instance."""
        self._debug = debug
        self._nmap = nmap3.NmapHostDiscovery()
        self._socket = None
        self._ethernet_mode = False
        self._serial_interface = None
        self._serial_mode = False
        atexit.register(self._exit)

    def _exit(self):
        try:
            self._socket.close()
        except AttributeError:
            pass
        self.disconnect_serial()

    def _debug_print(self, *args):
        """Print if debug is True."""
        if self._debug:
            print(*args)

    def _send_and_receive(self, msg):
        """Send message and receive response."""
        self._debug_print('sending:')
        self._debug_print(msg)
        if self._serial_mode:
            self._debug_print(f'over serial port {self._serial_interface.port}')
            read_data = self._serial_interface.write_read(msg)
            self._debug_print('received:')
            self._debug_print(read_data)
        # try:
        #     self._write_data = msg.encode()
        # except (UnicodeDecodeError, AttributeError):
        #     self._write_data = msg
        # self._debug_print(self._write_data)
        # self._bytes_written = self._serial.write(self._write_data)
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        #     s.connect((IP_ADDRESS, PORT))
        #     s.sendall(msg)
        #     data = s.recv(1024)

    # def _receive(self):
    #     """Receive response."""
    #     chars_waiting = self._serial.in_waiting
    #     self._debug_print('chars_waiting:', chars_waiting)
    #     return self._serial.read(chars_waiting)

    # def _send_receive(self, msg):
    #     """Send message then receive response."""
    #     self._send(msg)
    #     time.sleep(WRITE_READ_DELAY)
    #     response = self._receive()
    #     self._debug_print(response)

    def find_serial_ports(self):
        return find_serial_interface_ports()

    def connect_serial(self, port=None):
        """Connect to server through serial port."""
        self._debug_print('ArenaHost connecting through a serial port...')
        if port is not None:
            self._serial_interface = SerialInterface(port=port)
        else:
            self._serial_interface = SerialInterface()
        if self._serial_interface.is_open:
            self._debug_print(f'ArenaHost connected through serial port {self._serial_interface.port}')
            self._serial_mode = True
        else:
            self._debug_print('ArenaHost not connected!')

    def disconnect_serial(self):
        """Disconnect serial port."""
        try:
            self._serial_interface.close()
        except AttributeError:
            pass

    # def connect_ethernet(self, ip_address=None):
    #     """Connect to server at ip address."""
    #     if ip_address is None:
    #         if self._arena_ip_address is None:
    #             ip_address = self.discover_arena_ip_address
    #         else:
    #             ip_address = self._arena_ip_address
    #     if ip_address is not None:
    #         self._debug_print('Connecting to arena socket...')
    #         self._socket.connect((ip_address, PORT))
    #         self._debug_print('Arena socket connected')
    #         self._debug_print(self._socket.getpeername())
    #         return True
    #     else:
    #         self._debug_print('Arena IP address unknown')
    #         return False

    # def list_serial_ports(self):
    #     """List serial ports."""
    #     serial_interface_ports = os.listdir('{0}dev'.format(os.path.sep))
    #     serial_interface_ports = [x for x in serial_interface_ports if 'ttyUSB' in x or 'ttyACM' in x or 'arduino' in x]
    #     serial_interface_ports = ['{0}dev{0}{1}'.format(os.path.sep, x) for x in serial_interface_ports]
    #     print(serial_interface_ports)

    def discover_arena_ip_address(self):
        self._arena_ip_address = None
        results = self._nmap.nmap_portscan_only(IP_RANGE, args=f'-p {PORT}')
        filtered_results = dict(filter(results_filter, results.items()))
        arena_ip_addresses = list(filtered_results.keys())
        if len(arena_ip_addresses) == 1:
            self._arena_ip_address = arena_ip_addresses[0]
        return self._arena_ip_address

    def all_on(self):
        """Turn all panels on."""
        self._send_and_receive(b'\x01\xff')

    def all_off(self):
        """Turn all panels off."""
        self._send_and_receive(b'\x01\x00')

    def all_on_str(self):
        """Turn all panels on."""
        self._send_and_receive('ALL_ON')

    def all_off_str(self):
        """Turn all panels off."""
        self._send_and_receive('ALL_OFF')

    def say_hello(self):
        print("hello!")
