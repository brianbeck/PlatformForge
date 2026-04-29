"""PlatformForge CLI — Click application and command group."""

from __future__ import annotations

import click

from platformforge import __version__
from platformforge.commands.config import config_group
from platformforge.commands.deploy import deploy_cmd
from platformforge.commands.dns import dns_cmd
from platformforge.commands.init import init_cmd
from platformforge.commands.status import status_cmd
from platformforge.commands.teardown import teardown_cmd


@click.group()
@click.version_option(version=__version__, prog_name="platformforge")
def cli() -> None:
    """PlatformForge — GitOps platform services management for Kubernetes."""


cli.add_command(init_cmd)
cli.add_command(deploy_cmd)
cli.add_command(status_cmd)
cli.add_command(teardown_cmd)
cli.add_command(dns_cmd)
cli.add_command(config_group)
