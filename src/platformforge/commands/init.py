"""platformforge init — interactive bootstrap wizard."""

from __future__ import annotations

import click

from platformforge.core.config_io import find_project_root
from platformforge.wizard.steps import run_wizard


@click.command("init")
def init_cmd() -> None:
    """Interactive bootstrap wizard.

    Collects repository, environment, ingress, and secrets configuration.
    Writes environments.yml and encrypted vault secrets.
    """
    project_root = find_project_root()
    run_wizard(project_root)
