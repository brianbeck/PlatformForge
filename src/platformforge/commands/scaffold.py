"""platformforge scaffold — create the platformforge-env directory structure."""

from __future__ import annotations

from pathlib import Path

import click

from platformforge.core.config_io import find_project_root
from platformforge.ui.console import console


SERVICES = [
    "traefik",
    "observability",
    "cert-manager",
    "gatekeeper",
    "falco",
    "sealed-secrets",
    "external-secrets",
    "trivy-operator",
    "argo-rollouts",
]

GITIGNORE = """\
# Vault password
.vault_pass
vault-password.txt

# Ansible
*.retry

# Python
__pycache__/
*.pyc
.venv/
venv/

# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Claude
.claude/
"""


@click.command("scaffold")
@click.option(
    "--path",
    type=click.Path(),
    default=None,
    help="Path for the env repo (default: ../platformforge-env).",
)
def scaffold_cmd(path: str | None) -> None:
    """Create the platformforge-env directory structure.

    Scaffolds the directory layout for a new environment config repo.
    Does not run any git commands — prints the commands you need to run.
    """
    if path:
        env_root = Path(path).resolve()
    else:
        try:
            platform_root = find_project_root()
            env_root = platform_root.parent / "platformforge-env"
        except FileNotFoundError:
            env_root = Path.cwd().parent / "platformforge-env"

    if env_root.exists() and any(env_root.iterdir()):
        console.print(
            f"[yellow]Directory already exists and is not empty:[/yellow] {env_root}"
        )
        console.print("Remove it first or specify a different path with --path.")
        raise SystemExit(1)

    console.print(f"[bold]Scaffolding platformforge-env at:[/bold] {env_root}\n")

    # Create directories
    dirs = [
        "vault",
        "argocd/root",
        "argocd/waves-stage",
        "argocd/waves-prod",
    ]
    for svc in SERVICES:
        dirs.append(f"overlays/{svc}/stage")
        dirs.append(f"overlays/{svc}/prod")
    dirs.append("overlays/argo-rollouts/stage/manifests")
    dirs.append("overlays/argo-rollouts/prod/manifests")

    for d in dirs:
        (env_root / d).mkdir(parents=True, exist_ok=True)
        console.print(f"  [dim]{d}/[/dim]")

    # Write .gitignore
    (env_root / ".gitignore").write_text(GITIGNORE)
    console.print("  [dim].gitignore[/dim]")

    # Write README
    (env_root / "README.md").write_text(
        "# platformforge-env\n\n"
        "Private environment configuration for PlatformForge.\n\n"
        "See [PlatformForge](https://github.com/brianbeck/PlatformForge) "
        "for documentation.\n"
    )
    console.print("  [dim]README.md[/dim]")

    console.print(f"\n[green]Scaffolding complete.[/green]\n")
    console.print("[bold]Next steps:[/bold]\n")
    console.print(f"  cd {env_root}")
    console.print("  git init")
    console.print("  git add -A")
    console.print('  git commit -m "Initial platformforge-env structure"')
    console.print(
        "  gh repo create YOUR_ORG/platformforge-env --private --source=. --push"
    )
    console.print(f"\n  cd {env_root.parent / 'PlatformForge'}")
    console.print("  platformforge init")
    console.print("")
