"""Pydantic model for environments.yml configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class EnvironmentConfig(BaseModel):
    """Validated representation of environments.yml.

    Cross-field validators enforce consistency between environment model
    (A/B), cluster contexts, and ingress settings.
    """

    model_config = ConfigDict(extra="allow")

    # Environment model
    env_model: Literal["A", "B"]
    single_cluster: bool
    multi_cluster: bool
    stage_context: str
    prod_context: str
    stage_server: str = ""
    prod_server: str = ""
    platformforge_repo_url: str
    platformforge_repo_revision: str = "main"

    # Ingress
    ingress_enabled: bool = False
    traefik_enabled: bool = False
    admin_email: str = ""
    base_fqdn: str = ""
    argocd_hostname_stage: str = ""
    argocd_hostname_prod: str = ""
    grafana_ingress_enabled: bool = False
    grafana_hostname_stage: str = ""
    grafana_hostname_prod: str = ""
    prometheus_ingress_enabled: bool = False
    prometheus_hostname_stage: str = ""
    prometheus_hostname_prod: str = ""
    rollouts_ingress_enabled: bool = False
    rollouts_hostname_stage: str = ""
    rollouts_hostname_prod: str = ""
    pihole_enabled: bool = False
    pihole_primary_ip: str = ""
    pihole_secondary_ip: str = ""

    # Secrets
    secrets_strategy: Literal["sealed-secrets", "external-secrets"] = "sealed-secrets"
    vault_address: str = ""

    @model_validator(mode="after")
    def validate_model_consistency(self) -> EnvironmentConfig:
        if self.env_model == "A":
            if not self.single_cluster:
                raise ValueError("Model A requires single_cluster=True")
            if self.multi_cluster:
                raise ValueError("Model A requires multi_cluster=False")
        if self.env_model == "B":
            if not self.multi_cluster:
                raise ValueError("Model B requires multi_cluster=True")
            if self.single_cluster:
                raise ValueError("Model B requires single_cluster=False")
            if self.stage_context == self.prod_context:
                raise ValueError(
                    "Model B requires different stage and prod contexts"
                )
        if self.ingress_enabled:
            if not self.base_fqdn:
                raise ValueError("base_fqdn required when ingress is enabled")
            if not self.argocd_hostname_stage:
                raise ValueError(
                    "argocd_hostname_stage required when ingress is enabled"
                )
        return self
