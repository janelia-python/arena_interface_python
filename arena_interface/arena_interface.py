"""Python interface to the Reiser lab ArenaController."""
import os
import atexit
import serial
import socket
import nmap3

PORT = 62222
IP_ADDRESS = '192.168.10.62'
IP_RANGE = '192.168.10.0/24'

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
    BAUDRATE = 115200
    def __init__(self, debug=True):
        """Initialize a ArenaHost instance."""
        self._debug = debug
        self._nmap = nmap3.NmapHostDiscovery()
        self._arena_ip_address = IP_ADDRESS
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self._serial = serial.Serial()
        atexit.register(self._exit)

    def _exit(self):
        self._socket.close()
        # self._serial.close()

    def _debug_print(self, to_print):
        """Print if debug is True."""
        if self._debug:
            print(to_print)

    def _send(self, msg):
        """Send message."""
        # try:
        #     self._write_data = msg.encode()
        # except UnicodeDecodeError, AttributeError:
        #     self._write_data = msg
        # self._debug_print(self._write_data)
        # self._bytes_written = self._serial.write(self._write_data)
        if self._socket:
            print('sending:')
            print(msg)
            totalsent = 0
            while totalsent < len(msg):
                sent = self._socket.send(msg[totalsent:])
                if sent == 0:
                    raise RuntimeError("socket connection broken")
                totalsent = totalsent + sent

    # def connect_serial(self, port=None):
    #     """Connect to server through serial port."""
    #     self._serial = serial.Serial()
    #     self._debug_print('ArenaHost connecting serial port...')
    #     self._serial.baudrate = self.BAUDRATE
    #     self._serial.port = '/dev/ttyACM0'
    #     self._serial.open()
    #     if self._serial.is_open:
    #         self._debug_print('ArenaHost connected through serial port')
    #     else:
    #         self._debug_print('ArenaHost not connected!')

    # def disconnect_serial(self, port=None):
    #     """Disconnect serial port."""
    #     self._serial.close()

    def connect_ethernet(self, ip_address=None):
        """Connect to server at ip address."""
        if ip_address is None:
            if self._arena_ip_address is None:
                ip_address = self.discover_arena_ip_address
            else:
                ip_address = self._arena_ip_address
        if ip_address is not None:
            self._debug_print('Connecting to arena socket...')
            self._socket.connect((ip_address, PORT))
            self._debug_print('Arena socket connected')
            self._debug_print(self._socket.getpeername())
            return True
        else:
            self._debug_print('Arena IP address unknown')
            return False

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
        self._send(b'\x01\xff')

    def all_off(self):
        """Turn all panels off."""
        self._send(b'\x01\x00')

    # def all_on_str(self):
    #     """Turn all panels on."""
    #     self._send('ALL_ON')

    # def all_off_str(self):
    #     """Turn all panels off."""
    #     self._send('ALL_OFF')

    def say_hello(self):
        print("hello!")
