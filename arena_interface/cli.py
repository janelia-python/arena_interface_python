"""Command line interface for the ArenaHost."""
import click
import os

from .arena_interface import ArenaInterface

interface = ArenaInterface()


# CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
# @click.command(context_settings=CONTEXT_SETTINGS,
#                no_args_is_help=True)
# @click.option('-i', '--ip-address',
#               default=None,
#               help='ArenaController IP address')
# def cli(ip_address):
#     """Command line interface to the Reiser lab ArenaController."""
#     clear_screen()
#     interface.connect(ip_address)

def clear_screen():
    """Clear command line for various operating systems."""
    if (os.name == 'posix'):
        os.system('clear')
    else:
        os.system('cls')

@click.group()
def cli():
    pass

@click.command()
def list_ports():
    interface.list_serial_ports()

cli.add_command(list_ports)

@click.command()
def all_on():
    interface.connect_serial()
    interface.all_on()
    interface.disconnect_serial()

cli.add_command(all_on)

@click.command()
def all_off():
    interface.connect_serial()
    interface.all_off()
    interface.disconnect_serial()

cli.add_command(all_off)
