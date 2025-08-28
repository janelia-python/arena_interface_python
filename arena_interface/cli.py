"""Command line interface for the ArenaHost."""
import click
from pathlib import Path

from .arena_interface import ArenaInterface


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = ArenaInterface(debug=False)
    # ctx.obj = ArenaInterface(debug=True)

@cli.command()
@click.pass_obj
def all_off(ai):
    ai.all_off()

@cli.command()
@click.pass_obj
def display_reset(ai):
    ai.display_reset()

@cli.command()
@click.argument('grayscale-index', nargs=1, type=int)
@click.pass_obj
def switch_grayscale(ai, grayscale_index):
    ai.switch_grayscale(grayscale_index)

@cli.command()
@click.argument('pattern-id', nargs=1, type=int)
@click.argument('frame-rate', nargs=1, type=int)
@click.argument('runtime-duration', nargs=1, type=int)
@click.pass_obj
def trial_params(ai, pattern_id, frame_rate, runtime_duration):
    ai.trial_params(pattern_id, frame_rate, runtime_duration)

@cli.command()
@click.argument('refresh-rate', nargs=1, type=int)
@click.pass_obj
def set_refresh_rate(ai, refresh_rate):
    ai.set_refresh_rate(refresh_rate)

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

@cli.command()
@click.argument('path', nargs=1, type=click.Path(exists=True))
@click.argument('frame-rate', nargs=1, type=int)
@click.argument('runtime-duration', nargs=1, type=int)
@click.pass_obj
def stream_frames(ai, path, frame_rate, runtime_duration):
    abs_path = Path(path).absolute()
    ai.stream_frames(abs_path, frame_rate, runtime_duration)

