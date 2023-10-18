"""Python client interface to the Reiser lab PanelsController."""
import atexit
import serial
import socket


class PanelsControllerClient():
    """Python client interface to the Reiser lab PanelsController."""
    PORT = 62222
    def __init__(self, port=None, address=None, debug=False):
        """Initialize a PanelsControllerClient instance."""
        self._debug = debug
        self._debug_print('PanelsControllerClient initializing...')
        self._ser = None

        if port:
            print('PanelsControllerClient serial interface')
            self._ser = serial.Serial(port, 2000000, timeout=1)
        elif address:
            print('PanelsControllerClient socket interface')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect((address, PORT))
                except ConnectionRefusedError:
                    print(f"G4 Host doesn't appear to be running on {HOST}:{PORT}")

        self._debug_print('PanelsControllerClient initialized')

    @atexit.register
    def _atexit(self):
        if self._ser:
            self._ser.close()

    def _debug_print(self, to_print):
        """Print if debug is True."""
        if self._debug:
            print(to_print)

    def _write(self, request):
        """Write request to server."""
        if self._ser:
            self._ser.write(request)

    def all_on(self):
        """Turn all panels on."""
        self._write(b'\x01\xff')
        line = self._ser.readline()
        print(line)
        line = self._ser.readline()
        print(line)

