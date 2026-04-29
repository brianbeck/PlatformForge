"""Validation helpers: tool presence, git reachability, FQDN detection."""

from __future__ import annotations

import shutil
import subprocess


REQUIRED_TOOLS = ["kubectl", "helm", "git", "kubeseal"]


def check_tool(name: str) -> bool:
    """Return True if *name* is on PATH."""
    return shutil.which(name) is not None


def check_all_tools() -> dict[str, bool]:
    """Return {tool: available} for all required tools."""
    return {t: check_tool(t) for t in REQUIRED_TOOLS}


def validate_git_repo(url: str) -> bool:
    """Check that *url* is reachable via ``git ls-remote``."""
    try:
        subprocess.run(
            ["git", "ls-remote", "--exit-code", url],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def detect_fqdn() -> str:
    """Attempt to detect the local FQDN from hostname or resolv.conf."""
    # Try hostname -d
    try:
        result = subprocess.run(
            ["hostname", "-d"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to /etc/resolv.conf
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("search"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
    except OSError:
        pass

    return ""
