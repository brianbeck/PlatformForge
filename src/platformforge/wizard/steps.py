"""Init wizard — four sections mirroring the discover_* Ansible roles."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

from platformforge.core import kubectl, validation
from platformforge.core.config_io import env_path, find_env_root, load_raw, save_config
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
    env_root = find_env_root()
    saved = load_raw(env_path(env_root))

    data: dict = {}

    _section_repo(project_root, env_root, saved, data)
    _section_environment(saved, data)
    _section_ingress(env_root, saved, data)
    _section_logging(saved, data)
    _section_notifications(env_root, saved, data)
    _section_secrets(saved, data)
    _write_vault(env_root, data)

    config = EnvironmentConfig(**data)
    save_config(config, env_path(env_root))

    console.print()
    print_config_table(config)
    console.print()
    print_next_steps()

    return config


# ── Section 1: Repository ──────────────────────────────────────────


def _section_repo(
    project_root: Path,
    env_root: Path,
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

    # PlatformForge repo URL (public — base values, policies, CLI)
    default_url = saved.get("platformforge_repo_url", "")
    while True:
        url = ask("PlatformForge repo URL (public)", default=default_url)
        if not url:
            console.print("[red]URL is required.[/red]")
            continue
        console.print(f"  Validating [cyan]{url}[/cyan]...", end=" ")
        if validation.validate_git_repo(url):
            console.print("[green]OK[/green]")
            break
        console.print("[red]unreachable[/red]")
        default_url = url

    data["platformforge_repo_url"] = url
    data["platformforge_repo_revision"] = saved.get(
        "platformforge_repo_revision", "main"
    )

    # Env config repo URL (private — overlays, secrets, ApplicationSets)
    default_env_url = saved.get("env_repo_url", "")
    while True:
        env_url = ask("Env config repo URL (private)", default=default_env_url)
        if not env_url:
            console.print("[red]URL is required.[/red]")
            continue
        console.print(f"  Validating [cyan]{env_url}[/cyan]...", end=" ")
        if validation.validate_git_repo(env_url):
            console.print("[green]OK[/green]")
            break
        console.print("[red]unreachable[/red]")
        default_env_url = env_url

    data["env_repo_url"] = env_url
    data["env_repo_revision"] = saved.get("env_repo_revision", "main")
    data["env_repo_path"] = str(env_root)

    # GitHub PAT for Argo CD to access the private env repo
    console.print()
    console.print(
        "  [dim]Argo CD needs a GitHub Personal Access Token to read the\n"
        "  private env repo. Create one at: https://github.com/settings/tokens\n"
        "  Scope: repo (read access to private repos)[/dim]"
    )
    existing_pat = ""
    try:
        loaded = load_secrets(env_root)
        if loaded:
            existing_pat = loaded.github_pat
    except Exception:
        pass
    pat = ask("GitHub PAT", default=existing_pat, password=True)
    data["_github_pat"] = pat


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
    env_root: Path,
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
        _collect_secrets(env_root, saved, data, ingress_enabled=False)
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
    _collect_secrets(env_root, saved, data, ingress_enabled=True)


def _set_ingress_disabled(data: dict) -> None:
    """Set all ingress-related fields to their disabled defaults."""
    data["admin_email"] = ""
    data["base_fqdn"] = ""
    for svc in ("argocd", "grafana", "prometheus", "alertmanager", "rollouts"):
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

    # Alertmanager (follows Prometheus — same ingress toggle)
    if prom:
        data["alertmanager_hostname_stage"] = ask(
            "Alertmanager stage hostname",
            default=saved.get(
                "alertmanager_hostname_stage", f"alertmanager-stage.{fqdn}"
            ),
        )
        data["alertmanager_hostname_prod"] = ask(
            "Alertmanager prod hostname",
            default=saved.get(
                "alertmanager_hostname_prod", f"alertmanager-prod.{fqdn}"
            ),
        )
    else:
        data["alertmanager_hostname_stage"] = ""
        data["alertmanager_hostname_prod"] = ""

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
    env_root: Path,
    saved: dict,
    data: dict,
    *,
    ingress_enabled: bool,
) -> None:
    """Collect Cloudflare token and Pi-hole credentials; write vault."""
    # Load existing secrets from vault
    existing = VaultSecrets()
    try:
        loaded = load_secrets(env_root)
        if loaded:
            existing = loaded
    except Exception:
        pass

    secrets = VaultSecrets()

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

    # Store collected secrets in data for _write_vault to pick up
    data["_cloudflare_api_token"] = secrets.cloudflare_api_token
    data["_pihole_primary_ip"] = secrets.pihole_primary_ip
    data["_pihole_primary_password"] = secrets.pihole_primary_password
    data["_pihole_secondary_ip"] = secrets.pihole_secondary_ip
    data["_pihole_secondary_password"] = secrets.pihole_secondary_password


# ── Write Vault ────────────────────────────────────────────────────


def _write_vault(env_root: Path, data: dict) -> None:
    """Merge all collected secrets and write to vault."""
    # Vault password
    if not has_vault_pass(env_root):
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
        write_vault_pass(env_root, pw)

    secrets = VaultSecrets(
        cloudflare_api_token=data.pop("_cloudflare_api_token", ""),
        pihole_primary_ip=data.pop("_pihole_primary_ip", ""),
        pihole_primary_password=data.pop("_pihole_primary_password", ""),
        pihole_secondary_ip=data.pop("_pihole_secondary_ip", ""),
        pihole_secondary_password=data.pop("_pihole_secondary_password", ""),
        slack_webhook_stage=data.pop("_slack_webhook_stage", ""),
        slack_webhook_prod_critical=data.pop("_slack_webhook_prod_critical", ""),
        slack_webhook_prod_warnings=data.pop("_slack_webhook_prod_warnings", ""),
        slack_webhook_security=data.pop("_slack_webhook_security", ""),
        slack_webhook_vulnerabilities=data.pop("_slack_webhook_vulnerabilities", ""),
        smtp_password=data.pop("_smtp_password", ""),
        github_pat=data.pop("_github_pat", ""),
    )
    # Clean up the base name helper (not a config key)
    data.pop("_slack_base", None)
    save_secrets(env_root, secrets)


# ── Section 4: Logging ─────────────────────────────────────────────


def _section_logging(saved: dict, data: dict) -> None:
    console.print()
    console.print(Panel("[bold]Logging[/bold]", border_style="blue"))

    console.print(
        "  [dim]PlatformForge ships container logs to an external Loki\n"
        "  instance via Grafana Alloy. Enter the full URL with port.\n"
        "  Leave blank to skip (Alloy will not be deployed).[/dim]"
    )
    console.print()

    loki_url = ask(
        "Loki URL (e.g. http://loki.example.com:3100)",
        default=saved.get("loki_url", ""),
    )
    data["loki_url"] = loki_url


# ── Section 5: Notifications ──────────────────────────────────────


def _section_notifications(
    env_root: Path,
    saved: dict,
    data: dict,
) -> None:
    console.print()
    console.print(Panel("[bold]Notifications[/bold]", border_style="blue"))

    # Load existing secrets for defaults
    existing = VaultSecrets()
    try:
        loaded = load_secrets(env_root)
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

        base = ask(
            "Base channel name",
            default=saved.get("_slack_base", "platform"),
        )
        data["_slack_base"] = base  # not persisted, just for default computation

        # Channel definitions with descriptions
        channels = [
            (
                "stage",
                f"{base}-stage",
                "Stage alerts — receives ALL alerts (critical + warning) from\n"
                "  the stage cluster. Useful for catching issues during testing.",
            ),
            (
                "prod_critical",
                f"{base}-prod-critical",
                "Prod critical alerts — receives CRITICAL alerts from prod.\n"
                "  Active failures: pods down, sync errors, security events.",
            ),
            (
                "prod_warnings",
                f"{base}-prod-warnings",
                "Prod warnings — receives WARNING alerts from prod.\n"
                "  Early indicators: high vulnerability counts, resource pressure, scan gaps.",
            ),
            (
                "security",
                "security",
                "Security alerts — receives Falco runtime security alerts from\n"
                "  BOTH clusters: shell-in-container, privilege escalation, crypto mining.",
            ),
            (
                "vulnerabilities",
                "vulnerabilities",
                "Vulnerability alerts — receives Trivy vulnerability alerts from\n"
                "  BOTH clusters: critical CVEs, high vulnerability thresholds, scan failures.",
            ),
        ]

        for key, default_name, description in channels:
            saved_name = saved.get(f"slack_channel_{key}", default_name)
            console.print()
            console.print(f"  [dim]{description}[/dim]")
            name = ask(
                f"  Channel name (without #)",
                default=saved_name,
            )
            data[f"slack_channel_{key}"] = name

            webhook = ask(
                f"  Webhook URL for #{name}",
                default=getattr(existing, f"slack_webhook_{key}", ""),
                password=True,
            )
            data[f"_slack_webhook_{key}"] = webhook

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
        for key in ("stage", "prod_critical", "prod_warnings", "security", "vulnerabilities"):
            data[f"slack_channel_{key}"] = ""

    else:
        data["notification_provider"] = "none"
        for key in ("stage", "prod_critical", "prod_warnings", "security", "vulnerabilities"):
            data[f"slack_channel_{key}"] = ""
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
