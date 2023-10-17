"""Python client interface to the Reiser lab PanelsController."""
import socket


class PanelsControllerClient():
    """Python client interface to the Reiser lab PanelsController."""

    def __init__(self, debug=False):
        """Initialize a PanelsControllerClient instance."""
        self._debug = debug
        self._debug_print('PanelsControllerClient initializing...')
        self._debug_print('PanelsControllerClient initialized')

    def _debug_print(self, to_print):
        """Print if debug is True."""
        if self._debug:
            print(to_print)

