"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from platformforge.models.environment import EnvironmentConfig
from platformforge.models.secrets import VaultSecrets


class TestEnvironmentConfig:
    def test_valid_model_b(self, sample_config_data: dict) -> None:
        config = EnvironmentConfig(**sample_config_data)
        assert config.env_model == "B"
        assert config.multi_cluster is True

    def test_valid_model_a(self, sample_config_data: dict) -> None:
        data = sample_config_data.copy()
        data["env_model"] = "A"
        data["single_cluster"] = True
        data["multi_cluster"] = False
        data["prod_context"] = data["stage_context"]
        config = EnvironmentConfig(**data)
        assert config.single_cluster is True

    def test_model_b_same_context_fails(self, sample_config_data: dict) -> None:
        data = sample_config_data.copy()
        data["prod_context"] = data["stage_context"]
        with pytest.raises(ValidationError, match="different stage and prod"):
            EnvironmentConfig(**data)

    def test_model_a_inconsistent_flags(self, sample_config_data: dict) -> None:
        data = sample_config_data.copy()
        data["env_model"] = "A"
        data["single_cluster"] = False  # wrong
        data["multi_cluster"] = True
        with pytest.raises(ValidationError, match="single_cluster=True"):
            EnvironmentConfig(**data)

    def test_ingress_requires_fqdn(self, sample_config_data: dict) -> None:
        data = sample_config_data.copy()
        data["base_fqdn"] = ""
        with pytest.raises(ValidationError, match="base_fqdn"):
            EnvironmentConfig(**data)

    def test_ingress_disabled_no_fqdn_ok(self, sample_config_data: dict) -> None:
        data = sample_config_data.copy()
        data["ingress_enabled"] = False
        data["base_fqdn"] = ""
        data["argocd_hostname_stage"] = ""
        config = EnvironmentConfig(**data)
        assert config.base_fqdn == ""


class TestVaultSecrets:
    def test_defaults(self) -> None:
        s = VaultSecrets()
        assert s.cloudflare_api_token == ""
        assert s.pihole_primary_ip == ""

    def test_populated(self) -> None:
        s = VaultSecrets(
            cloudflare_api_token="tok123",
            pihole_primary_ip="10.0.0.1",
            pihole_primary_password="pass",
        )
        assert s.cloudflare_api_token == "tok123"
