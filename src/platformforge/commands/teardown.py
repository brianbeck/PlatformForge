"""platformforge teardown — remove all PlatformForge components."""

from __future__ import annotations

import click

from platformforge.core.ansible_runner import AnsibleError, run_playbook
from platformforge.core.config_io import env_path, find_project_root, load_config
from platformforge.ui.console import console
from platformforge.wizard.prompts import ask


@click.command("teardown")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.option(
    "--env",
    type=click.Choice(["stage", "prod", "all"], case_sensitive=False),
    default="all",
    help="Target environment (default: all).",
)
def teardown_cmd(yes: bool, env: str) -> None:
    """Remove PlatformForge components from cluster(s).

    Runs ansible/playbooks/teardown.yml.
    """
    project_root = find_project_root()
    config = load_config(env_path(project_root))
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    console.print(
        "[bold red]WARNING:[/bold red] This will remove PlatformForge "
        f"components from [cyan]{env}[/cyan] cluster(s).\n"
    )
    if env in ("all", "stage"):
        console.print(f"  Stage: [cyan]{config.stage_context}[/cyan]")
    if env in ("all", "prod") and config.multi_cluster:
        console.print(f"  Prod:  [cyan]{config.prod_context}[/cyan]")
    console.print()

    if not yes:
        answer = ask("Type 'yes' to proceed")
        if answer != "yes":
            console.print("Teardown aborted.")
            raise SystemExit(0)

    console.print("[bold]Tearing down PlatformForge...[/bold]\n")
    try:
        rc = run_playbook(
            "teardown.yml",
            project_root,
            extra_vars={
                "confirm_teardown_cli": "true",
                "target_env": env,
            },
        )
    except AnsibleError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if rc != 0:
        console.print(f"\n[red]Teardown failed (exit code {rc}).[/red]")
        raise SystemExit(rc)
    console.print("\n[green]Teardown complete.[/green]")
