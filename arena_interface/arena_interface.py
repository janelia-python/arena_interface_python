"""Python interface to the Reiser lab ArenaController."""
# import atexit
import socket
import nmap3
# from serial_interface import SerialInterface, find_serial_interface_ports


PORT = 62222
IP_ADDRESS = '192.168.10.62'
IP_RANGE = '192.168.10.0/24'
# SERIAL_BAUDRATE = 115200

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
        # self._socket = None
        self._ethernet_mode = True
        # self._serial_interface = None
    #     atexit.register(self._exit)

    # def _exit(self):
    #     try:
    #         self._serial_interface.close()
    #     except AttributeError:
    #         pass

    def _debug_print(self, *args):
        """Print if debug is True."""
        if self._debug:
            print(*args)

    def _send_and_receive(self, msg):
        """Send message and receive response."""
        self._debug_print('sending message:')
        self._debug_print(msg)
        if self._ethernet_mode:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                self._debug_print(f'to {IP_ADDRESS} port {PORT}')
                s.settimeout(2)
                s.connect((IP_ADDRESS, PORT))
                s.sendall(msg)
                try:
                    response = s.recv(1024)
                except TimeoutError:
                    response = None
        # else:
        #     self._debug_print(f'over serial port {self._serial_interface.port}')
        #     response = self._serial_interface.write_read(msg)
        self._debug_print('response:')
        self._debug_print(response)
        # try:
        #     self._write_data = msg.encode()
        # except (UnicodeDecodeError, AttributeError):
        #     self._write_data = msg
        # self._debug_print(self._write_data)
        # self._bytes_written = self._serial.write(self._write_data)

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

    # def find_serial_ports(self):
    #     return find_serial_interface_ports()

    # def connect_serial(self, port=None):
    #     """Connect to server through serial port."""
    #     self._debug_print('ArenaHost connecting through a serial port...')
    #     if port is not None:
    #         self._serial_interface = SerialInterface(port=port)
    #     else:
    #         self._serial_interface = SerialInterface()
    #     if self._serial_interface.is_open:
    #         self._debug_print(f'ArenaHost connected through serial port {self._serial_interface.port}')
    #         self._serial_mode = True
    #     else:
    #         self._debug_print('ArenaHost not connected!')

    # def disconnect_serial(self):
    #     """Disconnect serial port."""
    #     try:
    #         self._serial_interface.close()
    #     except AttributeError:
    #         pass

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

    def reset(self):
        """Reset arena."""
        self._send_and_receive(b'\x01\x01')

    def all_off(self):
        """Turn all panels off."""
        self._send_and_receive(b'\x01\x30')

    def all_on(self):
        """Turn all panels on."""
        self._send_and_receive(b'\x01\xff')

    def all_off_str(self):
        """Turn all panels off with string."""
        self._send_and_receive('ALL_OFF')

    def all_on_str(self):
        """Turn all panels on with string."""
        self._send_and_receive('ALL_ON')

    def say_hello(self):
        print("hello!")
