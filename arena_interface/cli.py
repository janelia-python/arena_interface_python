"""Command line interface for the ArenaHost."""
import click
from pathlib import Path

from .arena_interface import ArenaInterface


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = ArenaInterface()

@cli.command()
@click.pass_obj
def discover_arena(ai):
    arena_ip_address = ai.discover_arena_ip_address()
    print(arena_ip_address)

@cli.command()
@click.pass_obj
def reset(ai):
    ai.reset()

@cli.command()
@click.pass_obj
def all_off(ai):
    ai.all_off()

@cli.command()
@click.pass_obj
def all_on(ai):
    ai.all_on()

@cli.command()
@click.option('--path', type=click.Path(exists=True), help='Path to the file')
@click.pass_obj
def stream_pattern(ai, path):
    abs_path = Path(path).absolute()
    ai.stream_pattern(abs_path)
