"""Command line interface for the PanelsController client."""
import click
import os

from .panels_controller_client import PanelsControllerClient


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               no_args_is_help=True)
@click.option('-p', '--port',
              default=None,
              help='Device name (e.g. /dev/ttyUSB0 on GNU/Linux or COM3 on Windows)')
@click.option('-a', '--address',
              default=None,
              help='PanelsController IP address')
def cli(port,
        address):
    """Command line interface for the PanelsController client."""
    # clear_screen()
    dev = PanelsControllerClient(port=port,
                                 debug=debug)

def clear_screen():
    """Clear command line for various operating systems."""
    if (os.name == 'posix'):
        os.system('clear')
    else:
        os.system('cls')
