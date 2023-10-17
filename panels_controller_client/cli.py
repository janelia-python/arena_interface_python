"""Command line interface for the PanelsController client."""
import click

from .panels_controller_client import PanelsControllerClient


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               no_args_is_help=True)
@click.option('-a', '--address',
              default=None,
              help='PanelsController IP address')
def cli(address):
    """Command line interface for the PanelsController client."""
    # clear_screen()
    dev = PanelsControllerClient(debug=debug)

def clear_screen():
    """Clear command line for various operating systems."""
    if (os.name == 'posix'):
        os.system('clear')
    else:
        os.system('cls')
