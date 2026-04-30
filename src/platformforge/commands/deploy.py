"""platformforge deploy — install Argo CD and deploy platform services."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_env_root, find_project_root, load_config
from platformforge.ui.console import console


@click.command("deploy")
@click.option(
    "--env",
    type=click.Choice(["stage", "prod", "all"], case_sensitive=False),
    default="all",
    help="Target environment (default: all).",
)
def deploy_cmd(env: str) -> None:
    """Install Argo CD and deploy platform services.

    Runs ansible/playbooks/install-argocd.yml.
    """
    project_root = find_project_root()
    config = load_config(env_path())
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    if env != "all" and not config.multi_cluster:
        console.print(
            f"[yellow]Model A (single cluster) — --env {env} ignored, deploying to both.[/yellow]"
        )
        env = "all"

    label = f"[cyan]{env}[/cyan]" if env != "all" else "all environments"
    console.print(f"[bold]Deploying PlatformForge ({label})...[/bold]\n")
    try:
        extra = {"target_env": env}
        rc = run_playbook("install-argocd.yml", project_root, extra_vars=extra)
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[red]Deploy failed (exit code {rc}).[/red]")
        raise SystemExit(rc)
    console.print("\n[green]Deploy complete.[/green]")
