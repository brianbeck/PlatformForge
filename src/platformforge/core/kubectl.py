"""kubectl context discovery and validation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _kubeconfig_env() -> dict[str, str]:
    """Return an env dict with KUBECONFIG set.

    If KUBECONFIG is already in the environment, use it as-is.
    Otherwise, auto-discover kubeconfig files in ~/.kube/*.yml / *.yaml.
    """
    env = os.environ.copy()
    if "KUBECONFIG" not in env:
        kube_dir = Path.home() / ".kube"
        if kube_dir.is_dir():
            configs = sorted(
                list(kube_dir.glob("*.yml")) + list(kube_dir.glob("*.yaml"))
            )
            if configs:
                env["KUBECONFIG"] = ":".join(str(c) for c in configs)
    return env


def list_contexts() -> list[str]:
    """Return available kubectl context names."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "get-contexts", "-o", "name"],
            capture_output=True,
            text=True,
            check=True,
            env=_kubeconfig_env(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [c.strip() for c in result.stdout.strip().splitlines() if c.strip()]


def validate_context(name: str) -> bool:
    """Check whether a kubectl context exists."""
    return name in list_contexts()


def get_server_url(context: str) -> str:
    """Extract the API server URL for a given context."""
    env = _kubeconfig_env()
    try:
        result = subprocess.run(
            [
                "kubectl",
                "config",
                "view",
                "-o",
                f"jsonpath={{.contexts[?(@.name==\"{context}\")].context.cluster}}",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        cluster_name = result.stdout.strip()
        if not cluster_name:
            return ""
        result = subprocess.run(
            [
                "kubectl",
                "config",
                "view",
                "-o",
                f"jsonpath={{.clusters[?(@.name==\"{cluster_name}\")].cluster.server}}",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
