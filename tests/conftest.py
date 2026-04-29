"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal PlatformForge project structure in a temp dir."""
    (tmp_path / "ansible" / "playbooks").mkdir(parents=True)
    (tmp_path / "ansible" / "vault").mkdir(parents=True)
    (tmp_path / "platform").mkdir()
    return tmp_path


@pytest.fixture()
def sample_config_data() -> dict:
    """Return a valid EnvironmentConfig dict matching the real environments.yml."""
    return {
        "env_model": "B",
        "single_cluster": False,
        "multi_cluster": True,
        "stage_context": "beck-stage-admin@beck-stage",
        "prod_context": "beck-prod-admin@beck-prod",
        "stage_server": "",
        "prod_server": "",
        "platformforge_repo_url": "https://github.com/brianbeck/PlatformForge.git",
        "platformforge_repo_revision": "main",
        "ingress_enabled": True,
        "traefik_enabled": True,
        "admin_email": "brian@brianbeck.net",
        "base_fqdn": "brianbeck.net",
        "argocd_hostname_stage": "argocd-stage.brianbeck.net",
        "argocd_hostname_prod": "argocd-prod.brianbeck.net",
        "grafana_ingress_enabled": True,
        "grafana_hostname_stage": "grafana-stage.brianbeck.net",
        "grafana_hostname_prod": "grafana-prod.brianbeck.net",
        "prometheus_ingress_enabled": True,
        "prometheus_hostname_stage": "prometheus-stage.brianbeck.net",
        "prometheus_hostname_prod": "prometheus-prod.brianbeck.net",
        "rollouts_ingress_enabled": True,
        "rollouts_hostname_stage": "rollouts-stage.brianbeck.net",
        "rollouts_hostname_prod": "rollouts-prod.brianbeck.net",
        "pihole_enabled": True,
        "pihole_primary_ip": "192.168.20.201",
        "pihole_secondary_ip": "192.168.20.202",
        "secrets_strategy": "sealed-secrets",
        "vault_address": "",
    }
