"""Ansible Vault encrypt/decrypt via subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from platformforge.models.secrets import VaultSecrets


class VaultError(Exception):
    """Raised when an ansible-vault operation fails."""


def vault_pass_path(env_root: Path) -> Path:
    """Return the path to the vault password file (in env repo)."""
    return env_root / "vault" / ".vault_pass"


def secrets_path(env_root: Path) -> Path:
    """Return the path to the encrypted secrets file (in env repo)."""
    return env_root / "vault" / "secrets.yml"


def has_vault_pass(project_root: Path) -> bool:
    """Check whether the vault password file exists."""
    return vault_pass_path(project_root).exists()


def write_vault_pass(project_root: Path, password: str) -> None:
    """Write the vault password file with restrictive permissions."""
    path = vault_pass_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(password)
    path.chmod(0o600)


def load_secrets(project_root: Path) -> VaultSecrets | None:
    """Decrypt and load vault secrets.  Returns None if files don't exist."""
    sec_path = secrets_path(project_root)
    pass_path = vault_pass_path(project_root)
    if not sec_path.exists() or not pass_path.exists():
        return None
    try:
        result = subprocess.run(
            [
                "ansible-vault",
                "decrypt",
                "--vault-password-file",
                str(pass_path),
                "--output",
                "-",
                str(sec_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise VaultError(f"Failed to decrypt vault: {exc.stderr.strip()}") from exc
    data = yaml.safe_load(result.stdout)
    if not data:
        return VaultSecrets()
    return VaultSecrets(**data)


def save_secrets(project_root: Path, secrets: VaultSecrets) -> None:
    """Write secrets to vault file and encrypt it.

    Requires the vault password file to already exist.
    """
    sec_path = secrets_path(project_root)
    pass_path = vault_pass_path(project_root)
    if not pass_path.exists():
        raise VaultError("Vault password file not found. Run init first.")

    sec_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sec_path, "w") as f:
        yaml.dump(secrets.model_dump(), f, default_flow_style=False)
    sec_path.chmod(0o600)

    try:
        subprocess.run(
            [
                "ansible-vault",
                "encrypt",
                "--vault-password-file",
                str(pass_path),
                str(sec_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise VaultError(f"Failed to encrypt vault: {exc.stderr.strip()}") from exc
