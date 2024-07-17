from __future__ import annotations

import click
from beancount import loader
from fava.core.tree import Tree


@click.command()
@click.argument("beancount-file", type=click.Path(exists=True))
def cli(beancount_file):
    entries, _, options_map = loader.load_file(beancount_file)
    tree = Tree(entries)
    print(tree)


if __name__ == "__main__":
    cli()
