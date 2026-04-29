"""platformforge dns — re-register Pi-hole DNS records."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_project_root, load_config
from platformforge.ui.console import console


@click.command("dns")
def dns_cmd() -> None:
    """Re-register service hostnames with Pi-hole DNS.

    Runs ansible/playbooks/deploy-dns.yml.
    """
    project_root = find_project_root()
    config = load_config(env_path(project_root))
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    if not config.pihole_enabled:
        console.print("[yellow]Pi-hole DNS is not enabled in configuration.[/yellow]")
        raise SystemExit(0)

    console.print("[bold]Registering DNS records...[/bold]\n")
    try:
        rc = run_playbook("deploy-dns.yml", project_root)
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[red]DNS registration failed (exit code {rc}).[/red]")
        raise SystemExit(rc)
    console.print("\n[green]DNS registration complete.[/green]")
