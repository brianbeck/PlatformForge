"""platformforge status — health check across all clusters."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_project_root, load_config
from platformforge.ui.console import console


@click.command("status")
@click.option(
    "--env",
    type=click.Choice(["stage", "prod", "all"], case_sensitive=False),
    default="all",
    help="Target environment (default: all).",
)
def status_cmd(env: str) -> None:
    """Run health checks across clusters.

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
        extra = {"target_env": env}
        rc = run_playbook("healthcheck.yml", project_root, extra_vars=extra)
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[yellow]Health check returned exit code {rc}.[/yellow]")
        raise SystemExit(rc)
