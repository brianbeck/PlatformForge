"""kubectl context discovery and validation."""

from __future__ import annotations

import subprocess


def list_contexts() -> list[str]:
    """Return available kubectl context names."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "get-contexts", "-o", "name"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [c.strip() for c in result.stdout.strip().splitlines() if c.strip()]


def validate_context(name: str) -> bool:
    """Check whether a kubectl context exists."""
    return name in list_contexts()


def get_server_url(context: str) -> str:
    """Extract the API server URL for a given context."""
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
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
