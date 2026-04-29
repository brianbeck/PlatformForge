"""platformforge status — health check across all clusters."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_project_root, load_config
from platformforge.ui.console import console


@click.command("status")
def status_cmd() -> None:
    """Run health checks across all clusters.

    Runs ansible/playbooks/healthcheck.yml.
    """
    project_root = find_project_root()
    config = load_config(env_path(project_root))
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    console.print("[bold]Running health checks...[/bold]\n")
    try:
        rc = run_playbook("healthcheck.yml", project_root)
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[yellow]Health check returned exit code {rc}.[/yellow]")
        raise SystemExit(rc)
