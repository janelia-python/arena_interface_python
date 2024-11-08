"""Command line interface for the ArenaHost."""
import click
import os

from .arena_host import ArenaHost


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               no_args_is_help=True)
@click.option('-i', '--ip-address',
              default=None,
              help='PanelsController IP address')
def cli(ip_address):
    """Command line interface for the ArenaHost."""
    # clear_screen()
    dev = ArenaHost(debug=debug)

def clear_screen():
    """Clear command line for various operating systems."""
    if (os.name == 'posix'):
        os.system('clear')
    else:
        os.system('cls')
