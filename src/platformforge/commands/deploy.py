"""platformforge deploy — install Argo CD and deploy platform services."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_project_root, load_config
from platformforge.ui.console import console


@click.command("deploy")
def deploy_cmd() -> None:
    """Install Argo CD and deploy all platform services.

    Runs ansible/playbooks/install-argocd.yml.
    """
    project_root = find_project_root()
    config = load_config(env_path(project_root))
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    console.print("[bold]Deploying PlatformForge...[/bold]\n")
    try:
        rc = run_playbook("install-argocd.yml", project_root)
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[red]Deploy failed (exit code {rc}).[/red]")
        raise SystemExit(rc)
    console.print("\n[green]Deploy complete.[/green]")
