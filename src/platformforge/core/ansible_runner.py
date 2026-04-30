"""Subprocess wrapper for running ansible-playbook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from platformforge.core.vault import vault_pass_path


class AnsibleError(Exception):
    """Raised when an ansible-playbook run fails."""


def run_playbook(
    playbook: str,
    project_root: Path,
    extra_vars: dict[str, str] | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> int:
    """Run an Ansible playbook, streaming output to the caller.

    Parameters
    ----------
    playbook:
        Playbook filename relative to ``ansible/playbooks/``
        (e.g. ``"install-argocd.yml"``).
    project_root:
        PlatformForge repository root.
    extra_vars:
        Optional ``-e key=value`` pairs passed to ``ansible-playbook``.
    stream_callback:
        Called with each line of combined stdout/stderr.  If *None*,
        output goes to ``sys.stdout``.

    Returns
    -------
    int
        The process exit code.
    """
    ansible_dir = project_root / "ansible"
    playbook_path = ansible_dir / "playbooks" / playbook

    if not playbook_path.exists():
        raise AnsibleError(f"Playbook not found: {playbook_path}")

    cmd: list[str] = ["ansible-playbook", str(playbook_path)]

    # Vault password
    vp = vault_pass_path(project_root)
    if vp.exists():
        cmd.extend(["--vault-password-file", str(vp)])

    # Extra vars
    if extra_vars:
        for key, value in extra_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

    callback = stream_callback or (lambda line: sys.stdout.write(line + "\n"))

    # Ensure KUBECONFIG is set.  If not already in the environment,
    # auto-discover kubeconfig files in ~/.kube/*.yml / *.yaml.
    env = os.environ.copy()
    if "KUBECONFIG" not in env:
        kube_dir = Path.home() / ".kube"
        if kube_dir.is_dir():
            configs = sorted(
                list(kube_dir.glob("*.yml")) + list(kube_dir.glob("*.yaml"))
            )
            if configs:
                env["KUBECONFIG"] = ":".join(str(c) for c in configs)

    proc = subprocess.Popen(
        cmd,
        cwd=str(ansible_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        callback(line.rstrip("\n"))

    proc.wait()
    return proc.returncode
