"""Init wizard — four sections mirroring the discover_* Ansible roles."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

from platformforge.core import kubectl, validation
from platformforge.core.config_io import env_path, load_raw, save_config
from platformforge.core.vault import (
    has_vault_pass,
    load_secrets,
    save_secrets,
    write_vault_pass,
)
from platformforge.models.environment import EnvironmentConfig
from platformforge.models.secrets import VaultSecrets
from platformforge.ui.console import console
from platformforge.ui.formatting import print_config_table, print_next_steps
from platformforge.wizard.prompts import ask, ask_confirm


def run_wizard(project_root: Path) -> EnvironmentConfig:
    """Run the full init wizard and return the validated config."""
    saved = load_raw(env_path(project_root))

    data: dict = {}

    _section_repo(project_root, saved, data)
    _section_environment(saved, data)
    _section_ingress(project_root, saved, data)
    _section_notifications(project_root, saved, data)
    _section_secrets(saved, data)

    config = EnvironmentConfig(**data)
    save_config(config, env_path(project_root))

    console.print()
    print_config_table(config)
    console.print()
    print_next_steps()

    return config


# ── Section 1: Repository ──────────────────────────────────────────


def _section_repo(
    project_root: Path,
    saved: dict,
    data: dict,
) -> None:
    console.print(Panel("[bold]Repository[/bold]", border_style="blue"))

    # Check tools
    tools = validation.check_all_tools()
    for tool, available in tools.items():
        status = "[green]found[/green]" if available else "[red]NOT FOUND[/red]"
        console.print(f"  {tool}: {status}")
    missing = [t for t, ok in tools.items() if not ok]
    if missing:
        console.print(
            f"\n[red]Missing required tools: {', '.join(missing)}[/red]"
        )
        console.print("Install them and re-run [cyan]platformforge init[/cyan].")
        raise SystemExit(1)

    # Git repo URL
    default_url = saved.get("platformforge_repo_url", "")
    while True:
        url = ask("Git repository URL", default=default_url)
        if not url:
            console.print("[red]URL is required.[/red]")
            continue
        console.print(f"  Validating [cyan]{url}[/cyan]...", end=" ")
        if validation.validate_git_repo(url):
            console.print("[green]OK[/green]")
            break
        console.print("[red]unreachable[/red]")
        default_url = url  # keep their input for retry

    data["platformforge_repo_url"] = url
    data["platformforge_repo_revision"] = saved.get(
        "platformforge_repo_revision", "main"
    )


# ── Section 2: Environment Model + Contexts ────────────────────────


def _section_environment(saved: dict, data: dict) -> None:
    console.print()
    console.print(Panel("[bold]Environment[/bold]", border_style="blue"))

    # Model A/B
    default_model = saved.get("env_model", "B")
    model = ask_confirm(
        "Multi-cluster deployment? (Model B)",
        default=(default_model == "B"),
    )
    env_model = "B" if model else "A"

    data["env_model"] = env_model
    data["single_cluster"] = env_model == "A"
    data["multi_cluster"] = env_model == "B"

    # List contexts
    contexts = kubectl.list_contexts()
    if not contexts:
        console.print("[red]No kubectl contexts found. Configure kubeconfig first.[/red]")
        raise SystemExit(1)

    console.print("\nAvailable kubectl contexts:")
    for i, ctx in enumerate(contexts, 1):
        console.print(f"  [cyan]{i}[/cyan]. {ctx}")
    console.print()

    # Stage context
    default_stage = saved.get("stage_context", "")
    stage = _prompt_context("Stage context", contexts, default_stage)
    data["stage_context"] = stage
    data["stage_server"] = kubectl.get_server_url(stage)

    if env_model == "A":
        data["prod_context"] = stage
        data["prod_server"] = data["stage_server"]
    else:
        default_prod = saved.get("prod_context", "")
        while True:
            prod = _prompt_context("Prod context", contexts, default_prod)
            if prod != stage:
                break
            console.print("[red]Prod context must differ from stage in Model B.[/red]")
        data["prod_context"] = prod
        data["prod_server"] = kubectl.get_server_url(prod)


def _prompt_context(label: str, contexts: list[str], default: str) -> str:
    """Prompt the user to pick a kubectl context by name or number."""
    while True:
        value = ask(f"{label}", default=default)
        # Allow selection by number
        if value.isdigit():
            idx = int(value) - 1
            if 0 <= idx < len(contexts):
                return contexts[idx]
            console.print(f"[red]Enter 1–{len(contexts)}.[/red]")
            continue
        if value in contexts:
            return value
        console.print(f"[red]Context '{value}' not found.[/red]")


# ── Section 3: Ingress & DNS ───────────────────────────────────────


def _section_ingress(
    project_root: Path,
    saved: dict,
    data: dict,
) -> None:
    console.print()
    console.print(Panel("[bold]Ingress & DNS[/bold]", border_style="blue"))

    traefik = ask_confirm(
        "Enable Traefik ingress controller?",
        default=saved.get("traefik_enabled", True),
    )
    data["traefik_enabled"] = traefik
    data["ingress_enabled"] = traefik

    if not traefik:
        _set_ingress_disabled(data)
        _collect_secrets(project_root, saved, data, ingress_enabled=False)
        return

    # Admin email
    data["admin_email"] = ask(
        "Admin email (for Let's Encrypt)",
        default=saved.get("admin_email", ""),
    )

    # Base FQDN
    detected = validation.detect_fqdn()
    default_fqdn = saved.get("base_fqdn", detected)
    while True:
        fqdn = ask("Base domain", default=default_fqdn)
        if fqdn:
            break
        console.print("[red]A base domain is required.[/red]")
    data["base_fqdn"] = fqdn

    # Hostnames
    _collect_hostnames(saved, data, fqdn)

    # Secrets (Cloudflare + Pi-hole)
    _collect_secrets(project_root, saved, data, ingress_enabled=True)


def _set_ingress_disabled(data: dict) -> None:
    """Set all ingress-related fields to their disabled defaults."""
    data["admin_email"] = ""
    data["base_fqdn"] = ""
    for svc in ("argocd", "grafana", "prometheus", "rollouts"):
        data[f"{svc}_hostname_stage"] = ""
        data[f"{svc}_hostname_prod"] = ""
    data["grafana_ingress_enabled"] = False
    data["prometheus_ingress_enabled"] = False
    data["rollouts_ingress_enabled"] = False
    data["pihole_enabled"] = False
    data["pihole_primary_ip"] = ""
    data["pihole_secondary_ip"] = ""


def _collect_hostnames(saved: dict, data: dict, fqdn: str) -> None:
    """Prompt for service hostnames."""
    # ArgoCD (always on if ingress enabled)
    data["argocd_hostname_stage"] = ask(
        "ArgoCD stage hostname",
        default=saved.get("argocd_hostname_stage", f"argocd-stage.{fqdn}"),
    )
    data["argocd_hostname_prod"] = ask(
        "ArgoCD prod hostname",
        default=saved.get("argocd_hostname_prod", f"argocd-prod.{fqdn}"),
    )

    # Grafana
    grafana = ask_confirm(
        "Enable Grafana external access?",
        default=saved.get("grafana_ingress_enabled", True),
    )
    data["grafana_ingress_enabled"] = grafana
    if grafana:
        data["grafana_hostname_stage"] = ask(
            "Grafana stage hostname",
            default=saved.get("grafana_hostname_stage", f"grafana-stage.{fqdn}"),
        )
        data["grafana_hostname_prod"] = ask(
            "Grafana prod hostname",
            default=saved.get("grafana_hostname_prod", f"grafana-prod.{fqdn}"),
        )
    else:
        data["grafana_hostname_stage"] = ""
        data["grafana_hostname_prod"] = ""

    # Prometheus
    prom = ask_confirm(
        "Enable Prometheus external access?",
        default=saved.get("prometheus_ingress_enabled", True),
    )
    data["prometheus_ingress_enabled"] = prom
    if prom:
        data["prometheus_hostname_stage"] = ask(
            "Prometheus stage hostname",
            default=saved.get(
                "prometheus_hostname_stage", f"prometheus-stage.{fqdn}"
            ),
        )
        data["prometheus_hostname_prod"] = ask(
            "Prometheus prod hostname",
            default=saved.get(
                "prometheus_hostname_prod", f"prometheus-prod.{fqdn}"
            ),
        )
    else:
        data["prometheus_hostname_stage"] = ""
        data["prometheus_hostname_prod"] = ""

    # Rollouts dashboard
    rollouts = ask_confirm(
        "Enable Argo Rollouts dashboard external access?",
        default=saved.get("rollouts_ingress_enabled", True),
    )
    data["rollouts_ingress_enabled"] = rollouts
    if rollouts:
        data["rollouts_hostname_stage"] = ask(
            "Rollouts stage hostname",
            default=saved.get(
                "rollouts_hostname_stage", f"rollouts-stage.{fqdn}"
            ),
        )
        data["rollouts_hostname_prod"] = ask(
            "Rollouts prod hostname",
            default=saved.get(
                "rollouts_hostname_prod", f"rollouts-prod.{fqdn}"
            ),
        )
    else:
        data["rollouts_hostname_stage"] = ""
        data["rollouts_hostname_prod"] = ""


def _collect_secrets(
    project_root: Path,
    saved: dict,
    data: dict,
    *,
    ingress_enabled: bool,
) -> None:
    """Collect Cloudflare token and Pi-hole credentials; write vault."""
    # Load existing secrets from vault
    existing = VaultSecrets()
    try:
        loaded = load_secrets(project_root)
        if loaded:
            existing = loaded
    except Exception:
        pass

    secrets = VaultSecrets()

    # Carry forward notification secrets collected in _section_notifications
    secrets.slack_webhook_url = data.pop("_slack_webhook_url", existing.slack_webhook_url)
    secrets.smtp_password = data.pop("_smtp_password", existing.smtp_password)

    if ingress_enabled:
        # Cloudflare API token
        token = ask(
            "Cloudflare API token",
            default=existing.cloudflare_api_token,
            password=True,
        )
        secrets.cloudflare_api_token = token

        # Pi-hole
        pihole = ask_confirm(
            "Enable Pi-hole DNS registration?",
            default=saved.get("pihole_enabled", True),
        )
        data["pihole_enabled"] = pihole

        if pihole:
            secrets.pihole_primary_ip = ask(
                "Primary Pi-hole IP",
                default=existing.pihole_primary_ip,
            )
            data["pihole_primary_ip"] = secrets.pihole_primary_ip

            secrets.pihole_primary_password = ask(
                "Primary Pi-hole password",
                default=existing.pihole_primary_password,
                password=True,
            )

            secondary_ip = ask(
                "Secondary Pi-hole IP (blank to skip)",
                default=existing.pihole_secondary_ip,
            )
            secrets.pihole_secondary_ip = secondary_ip
            data["pihole_secondary_ip"] = secondary_ip

            if secondary_ip:
                secrets.pihole_secondary_password = ask(
                    "Secondary Pi-hole password",
                    default=existing.pihole_secondary_password,
                    password=True,
                )
        else:
            data["pihole_primary_ip"] = ""
            data["pihole_secondary_ip"] = ""

    # Vault password
    if not has_vault_pass(project_root):
        console.print()
        console.print(
            Panel(
                "A vault password is needed to encrypt secrets.\n"
                "Saved to ansible/.vault_pass (gitignored).",
                title="Ansible Vault",
                border_style="yellow",
            )
        )
        while True:
            pw = ask("Vault password", password=True)
            if pw:
                break
            console.print("[red]Password cannot be empty.[/red]")
        write_vault_pass(project_root, pw)

    save_secrets(project_root, secrets)


# ── Section 4: Notifications ───────────────────────────────────────


def _section_notifications(
    project_root: Path,
    saved: dict,
    data: dict,
) -> None:
    console.print()
    console.print(Panel("[bold]Notifications[/bold]", border_style="blue"))

    # Load existing secrets for defaults
    existing = VaultSecrets()
    try:
        loaded = load_secrets(project_root)
        if loaded:
            existing = loaded
    except Exception:
        pass

    default_provider = saved.get("notification_provider", "none")
    console.print("  How do you want to receive notifications?")
    console.print("  [cyan]1[/cyan]. Slack")
    console.print("  [cyan]2[/cyan]. Email")
    console.print("  [cyan]3[/cyan]. None")
    console.print()

    default_choice = {"slack": "1", "email": "2", "none": "3"}.get(default_provider, "3")
    choice = ask("Choice", default=default_choice)

    if choice == "1" or choice.lower() == "slack":
        data["notification_provider"] = "slack"
        data["slack_channel"] = ask(
            "Slack channel name (without #)",
            default=saved.get("slack_channel", "platform-alerts"),
        )
        webhook = ask(
            "Slack webhook URL",
            default=existing.slack_webhook_url,
            password=True,
        )
        # Store temporarily in data; _collect_secrets will move to vault
        data["_slack_webhook_url"] = webhook
        data["smtp_host"] = ""
        data["smtp_from"] = ""
        data["smtp_to"] = ""

    elif choice == "2" or choice.lower() == "email":
        data["notification_provider"] = "email"
        data["smtp_host"] = ask(
            "SMTP host (e.g. smtp.gmail.com:587)",
            default=saved.get("smtp_host", ""),
        )
        data["smtp_from"] = ask(
            "From address",
            default=saved.get("smtp_from", ""),
        )
        data["smtp_to"] = ask(
            "To address",
            default=saved.get("smtp_to", ""),
        )
        smtp_pw = ask(
            "SMTP password",
            default=existing.smtp_password,
            password=True,
        )
        data["_smtp_password"] = smtp_pw
        data["slack_channel"] = ""

    else:
        data["notification_provider"] = "none"
        data["slack_channel"] = ""
        data["smtp_host"] = ""
        data["smtp_from"] = ""
        data["smtp_to"] = ""


# ── Section 5: Secrets Strategy ────────────────────────────────────


def _section_secrets(saved: dict, data: dict) -> None:
    console.print()
    console.print(Panel("[bold]Secrets Strategy[/bold]", border_style="blue"))

    default_strategy = saved.get("secrets_strategy", "sealed-secrets")
    is_sealed = default_strategy == "sealed-secrets"
    sealed = ask_confirm("Use Sealed Secrets? (N for External Secrets)", default=is_sealed)
    strategy = "sealed-secrets" if sealed else "external-secrets"
    data["secrets_strategy"] = strategy

    if strategy == "external-secrets":
        data["vault_address"] = ask(
            "Vault address (e.g. https://vault.example.com)",
            default=saved.get("vault_address", ""),
        )
    else:
        data["vault_address"] = ""
