"""Python client interface to the Reiser lab PanelsController."""
import socket


class PanelsControllerClient():
    """Python client interface to the Reiser lab PanelsController."""
    PORT = 62222
    def __init__(self, address, debug=False):
        """Initialize a PanelsControllerClient instance."""
        self._debug = debug
        self._debug_print('PanelsControllerClient initializing...')

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((address, PORT))
            except ConnectionRefusedError:
                print(f"G4 Host doesn't appear to be running on {HOST}:{PORT}")

        self._debug_print('PanelsControllerClient initialized')

    def _debug_print(self, to_print):
        """Print if debug is True."""
        if self._debug:
            print(to_print)

