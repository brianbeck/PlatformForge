"""Rich formatting helpers for config display and status output."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from platformforge.models.environment import EnvironmentConfig
from platformforge.ui.console import console


def print_config_table(config: EnvironmentConfig) -> None:
    """Print a Rich table summarising the current configuration."""
    table = Table(title="PlatformForge Configuration", show_lines=True)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_section()
    table.add_row("Environment Model", config.env_model)
    table.add_row("Stage Context", config.stage_context)
    table.add_row("Prod Context", config.prod_context)
    table.add_row("Git Repo", config.platformforge_repo_url)
    table.add_row("Branch", config.platformforge_repo_revision)

    table.add_section()
    table.add_row("Ingress Enabled", str(config.ingress_enabled))
    if config.ingress_enabled:
        table.add_row("Base Domain", config.base_fqdn)
        table.add_row("Admin Email", config.admin_email)
        table.add_row("ArgoCD Stage", config.argocd_hostname_stage)
        table.add_row("ArgoCD Prod", config.argocd_hostname_prod)
        if config.grafana_ingress_enabled:
            table.add_row("Grafana Stage", config.grafana_hostname_stage)
            table.add_row("Grafana Prod", config.grafana_hostname_prod)
        if config.prometheus_ingress_enabled:
            table.add_row("Prometheus Stage", config.prometheus_hostname_stage)
            table.add_row("Prometheus Prod", config.prometheus_hostname_prod)
        if config.rollouts_ingress_enabled:
            table.add_row("Rollouts Stage", config.rollouts_hostname_stage)
            table.add_row("Rollouts Prod", config.rollouts_hostname_prod)

    table.add_section()
    table.add_row("Pi-hole DNS", str(config.pihole_enabled))
    if config.pihole_enabled:
        table.add_row("Primary Pi-hole", config.pihole_primary_ip)
        if config.pihole_secondary_ip:
            table.add_row("Secondary Pi-hole", config.pihole_secondary_ip)

    table.add_section()
    if config.loki_url:
        table.add_row("Loki URL", config.loki_url)
    else:
        table.add_row("Logging", "disabled")

    table.add_section()
    table.add_row("Notifications", config.notification_provider)
    if config.notification_provider == "slack":
        table.add_row("Stage Alerts", f"#{config.slack_channel_stage}")
        table.add_row("Prod Critical", f"#{config.slack_channel_prod_critical}")
        table.add_row("Prod Warnings", f"#{config.slack_channel_prod_warnings}")
        table.add_row("Security", f"#{config.slack_channel_security}")
        table.add_row("Vulnerabilities", f"#{config.slack_channel_vulnerabilities}")
    elif config.notification_provider == "email":
        table.add_row("SMTP Host", config.smtp_host)
        table.add_row("From", config.smtp_from)
        table.add_row("To", config.smtp_to)

    table.add_section()
    table.add_row("Secrets Strategy", config.secrets_strategy)
    if config.vault_address:
        table.add_row("Vault Address", config.vault_address)

    console.print(table)


def print_next_steps() -> None:
    """Print the post-init next-steps panel."""
    console.print(
        Panel(
            "[bold]Next steps:[/bold]\n\n"
            "  1. [cyan]platformforge deploy[/cyan]     Install Argo CD + deploy platform\n"
            "  2. [cyan]git add argocd/ && git commit && git push[/cyan]\n"
            "  3. [cyan]platformforge status[/cyan]     Verify all services\n",
            title="Init Complete",
            border_style="green",
        )
    )
