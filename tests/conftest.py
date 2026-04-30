"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal PlatformForge project structure in a temp dir."""
    (tmp_path / "ansible" / "playbooks").mkdir(parents=True)
    (tmp_path / "platform").mkdir()
    # Env repo structure
    env = tmp_path / "platformforge-env"
    (env / "vault").mkdir(parents=True)
    (env / "overlays").mkdir()
    (env / "argocd").mkdir()
    return tmp_path


@pytest.fixture()
def sample_config_data() -> dict:
    """Return a valid EnvironmentConfig dict with example values."""
    return {
        "env_model": "B",
        "single_cluster": False,
        "multi_cluster": True,
        "stage_context": "stage-admin@stage",
        "prod_context": "prod-admin@prod",
        "stage_server": "",
        "prod_server": "",
        "platformforge_repo_url": "https://github.com/example-org/PlatformForge.git",
        "platformforge_repo_revision": "main",
        "env_repo_url": "https://github.com/example-org/platformforge-env.git",
        "env_repo_revision": "main",
        "env_repo_path": "/tmp/platformforge-env",
        "ingress_enabled": True,
        "traefik_enabled": True,
        "admin_email": "admin@example.com",
        "base_fqdn": "example.com",
        "argocd_hostname_stage": "argocd-stage.example.com",
        "argocd_hostname_prod": "argocd-prod.example.com",
        "grafana_ingress_enabled": True,
        "grafana_hostname_stage": "grafana-stage.example.com",
        "grafana_hostname_prod": "grafana-prod.example.com",
        "prometheus_ingress_enabled": True,
        "prometheus_hostname_stage": "prometheus-stage.example.com",
        "prometheus_hostname_prod": "prometheus-prod.example.com",
        "alertmanager_hostname_stage": "alertmanager-stage.example.com",
        "alertmanager_hostname_prod": "alertmanager-prod.example.com",
        "rollouts_ingress_enabled": True,
        "rollouts_hostname_stage": "rollouts-stage.example.com",
        "rollouts_hostname_prod": "rollouts-prod.example.com",
        "pihole_enabled": True,
        "pihole_primary_ip": "10.0.0.1",
        "pihole_secondary_ip": "10.0.0.2",
        "notification_provider": "none",
        "slack_channel_stage": "",
        "slack_channel_prod_critical": "",
        "slack_channel_prod_warnings": "",
        "slack_channel_security": "",
        "slack_channel_vulnerabilities": "",
        "smtp_host": "",
        "smtp_from": "",
        "smtp_to": "",
        "secrets_strategy": "sealed-secrets",
        "vault_address": "",
    }
