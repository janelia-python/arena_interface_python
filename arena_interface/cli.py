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
@click.argument('path', nargs=1, type=click.Path(exists=True))
@click.argument('frame-index', nargs=1, type=int)
@click.pass_obj
def stream_frame(ai, path, frame_index):
    abs_path = Path(path).absolute()
    ai.stream_frame(abs_path, frame_index)
