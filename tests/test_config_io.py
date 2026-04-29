"""Tests for config_io module — round-trip read/write."""

from __future__ import annotations

from pathlib import Path

from platformforge.core.config_io import load_config, save_config
from platformforge.models.environment import EnvironmentConfig


class TestConfigRoundTrip:
    def test_write_then_read(self, tmp_path: Path, sample_config_data: dict) -> None:
        path = tmp_path / "environments.yml"
        config = EnvironmentConfig(**sample_config_data)
        save_config(config, path)

        # File should exist and contain section markers
        text = path.read_text()
        assert "# BEGIN INGRESS CONFIGURATION" in text
        assert "# END INGRESS CONFIGURATION" in text
        assert "# BEGIN SECRETS CONFIGURATION" in text
        assert "# END SECRETS CONFIGURATION" in text

        # Round-trip: load it back and compare
        loaded = load_config(path)
        assert loaded is not None
        assert loaded.env_model == config.env_model
        assert loaded.stage_context == config.stage_context
        assert loaded.prod_context == config.prod_context
        assert loaded.base_fqdn == config.base_fqdn
        assert loaded.secrets_strategy == config.secrets_strategy

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.yml"
        assert load_config(path) is None

    def test_preserves_boolean_format(
        self, tmp_path: Path, sample_config_data: dict
    ) -> None:
        """Ansible expects True/False (Python-style), not true/false (YAML)."""
        path = tmp_path / "environments.yml"
        config = EnvironmentConfig(**sample_config_data)
        save_config(config, path)
        text = path.read_text()
        assert "single_cluster: False" in text
        assert "multi_cluster: True" in text
        assert "ingress_enabled: True" in text
