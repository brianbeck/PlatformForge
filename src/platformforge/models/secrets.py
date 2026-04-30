"""Pydantic model for Ansible Vault secrets."""

from __future__ import annotations

from pydantic import BaseModel


class VaultSecrets(BaseModel):
    """Validated representation of ansible/vault/secrets.yml (decrypted)."""

    cloudflare_api_token: str = ""
    pihole_primary_ip: str = ""
    pihole_primary_password: str = ""
    pihole_secondary_ip: str = ""
    pihole_secondary_password: str = ""
    slack_webhook_stage: str = ""
    slack_webhook_prod_critical: str = ""
    slack_webhook_prod_warnings: str = ""
    slack_webhook_security: str = ""
    slack_webhook_vulnerabilities: str = ""
    smtp_password: str = ""
    github_pat: str = ""
