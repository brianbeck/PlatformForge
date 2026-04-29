"""platformforge config — show and set configuration values."""

from __future__ import annotations

import click

from platformforge.core.config_io import env_path, find_project_root, load_config, save_config
from platformforge.models.environment import EnvironmentConfig
from platformforge.ui.console import console
from platformforge.ui.formatting import print_config_table


@click.group("config")
def config_group() -> None:
    """View and modify PlatformForge configuration."""


@config_group.command("show")
def config_show() -> None:
    """Display the current configuration."""
    project_root = find_project_root()
    config = load_config(env_path(project_root))
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)
    print_config_table(config)


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a single configuration value.

    Example: platformforge config set base_fqdn example.com
    """
    project_root = find_project_root()
    path = env_path(project_root)
    config = load_config(path)
    if config is None:
        console.print(
            "[red]No configuration found. Run [cyan]platformforge init[/cyan] first.[/red]"
        )
        raise SystemExit(1)

    data = config.model_dump()
    if key not in data:
        console.print(f"[red]Unknown key: {key}[/red]")
        console.print(f"Valid keys: {', '.join(sorted(data.keys()))}")
        raise SystemExit(1)

    # Coerce booleans
    old_val = data[key]
    if isinstance(old_val, bool):
        value_parsed: str | bool = value.lower() in ("true", "1", "yes")
        data[key] = value_parsed
    else:
        data[key] = value

    try:
        updated = EnvironmentConfig(**data)
    except Exception as exc:
        console.print(f"[red]Validation error: {exc}[/red]")
        raise SystemExit(1)

    save_config(updated, path)
    console.print(f"[green]{key}[/green] = {data[key]}")


@config_group.command("path")
def config_path() -> None:
    """Print the path to environments.yml."""
    project_root = find_project_root()
    console.print(str(env_path(project_root)))
