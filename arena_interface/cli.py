"""Command line interface for the ArenaHost."""
import click
import os

from .arena_interface import ArenaInterface


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = ArenaInterface()

@cli.command()
@click.pass_obj
def say_hello(ai):
    ai.say_hello()

@cli.command()
@click.pass_obj
def discover_arena(ai):
    arena_ip_address = ai.discover_arena_ip_address()
    print(arena_ip_address)

@cli.command()
@click.pass_obj
def connect_ethernet(ai):
    ai.connect_ethernet()

@cli.command()
@click.pass_obj
def all_on(ai):
    ai.all_on()

# def clear_screen():
#     """Clear command line for various operating systems."""
#     if (os.name == 'posix'):
#         os.system('clear')
#     else:
#         os.system('cls')

# @click.group()
# def cli():
#     pass

# @click.command()
# def list_ports():
#     interface.list_serial_ports()

# cli.add_command(list_ports)

# @click.command()
# def all_on():
#     interface.connect_serial()
#     interface.all_on()
#     interface.disconnect_serial()

# cli.add_command(all_on)

# @click.command()
# def all_off():
#     interface.connect_serial()
#     interface.all_off()
#     interface.disconnect_serial()

# cli.add_command(all_off)
