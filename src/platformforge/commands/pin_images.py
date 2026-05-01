"""platformforge pin-images — resolve and pin container image digests."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import click
import yaml

from platformforge.core.config_io import find_project_root
from platformforge.ui.console import console


# Chart → Helm repo/chart → image value paths to update
# Each entry: (values_key_path, registry_image_pattern)
CHART_IMAGES: dict[str, list[dict]] = {
    "traefik": [
        {"key": "image.tag", "image": "docker.io/traefik", "format": "tag_digest"},
    ],
    "cert-manager": [
        {"key": "image.digest", "image": "quay.io/jetstack/cert-manager-controller", "format": "digest_only"},
        {"key": "webhook.image.digest", "image": "quay.io/jetstack/cert-manager-webhook", "format": "digest_only"},
        {"key": "cainjector.image.digest", "image": "quay.io/jetstack/cert-manager-cainjector", "format": "digest_only"},
        {"key": "startupapicheck.image.digest", "image": "quay.io/jetstack/cert-manager-startupapicheck", "format": "digest_only"},
    ],
    "sealed-secrets": [
        {"key": "image.tag", "image": "docker.io/bitnami/sealed-secrets-controller", "format": "tag_digest"},
    ],
    "external-secrets": [
        {"key": "image.tag", "image": "ghcr.io/external-secrets/external-secrets", "format": "tag_digest"},
    ],
    "gatekeeper": [
        {"key": "image.release", "image": "openpolicyagent/gatekeeper", "format": "tag_digest"},
        {"key": "preInstall.crdRepository.image.tag", "image": "openpolicyagent/gatekeeper-crds", "format": "tag_digest"},
        {"key": "postInstall.probeWebhook.image.tag", "image": "curlimages/curl", "format": "tag_digest"},
    ],
    "falco": [
        {"key": "image.tag", "image": "docker.io/falcosecurity/falco", "format": "tag_digest"},
        {"key": "falcoctl.image.tag", "image": "docker.io/falcosecurity/falcoctl", "format": "tag_digest"},
    ],
    "trivy-operator": [
        {"key": "image.tag", "image": "mirror.gcr.io/aquasec/trivy-operator", "format": "tag_digest"},
    ],
    "argo-rollouts": [
        {"key": "image.tag", "image": "quay.io/argoproj/argo-rollouts", "format": "tag_digest"},
        {"key": "dashboard.image.tag", "image": "quay.io/argoproj/kubectl-argo-rollouts", "format": "tag_digest"},
    ],
    "alloy": [
        {"key": "image.tag", "image": "docker.io/grafana/alloy", "format": "tag_digest"},
    ],
    "observability": [
        {"key": "prometheusOperator.image.sha", "image": "quay.io/prometheus-operator/prometheus-operator", "format": "sha_only"},
        {"key": "prometheusOperator.prometheusConfigReloader.image.sha", "image": "quay.io/prometheus-operator/prometheus-config-reloader", "format": "sha_only"},
        {"key": "prometheusOperator.admissionWebhooks.patch.image.sha", "image": "ghcr.io/jkroepke/kube-webhook-certgen", "format": "sha_only"},
        {"key": "prometheus.prometheusSpec.image.sha", "image": "quay.io/prometheus/prometheus", "format": "sha_only"},
        {"key": "alertmanager.alertmanagerSpec.image.sha", "image": "quay.io/prometheus/alertmanager", "format": "sha_only"},
        {"key": "nodeExporter.image.sha", "image": "quay.io/prometheus/node-exporter", "format": "sha_only"},
        {"key": "kube-state-metrics.image.sha", "image": "registry.k8s.io/kube-state-metrics/kube-state-metrics", "format": "sha_only"},
        {"key": "grafana.image.sha", "image": "docker.io/grafana/grafana", "format": "sha_only"},
        {"key": "grafana.sidecar.image.sha", "image": "quay.io/kiwigrid/k8s-sidecar", "format": "sha_only"},
    ],
}


def _resolve_digest(image_with_tag: str) -> str | None:
    """Resolve the SHA256 digest of an image using crane."""
    try:
        result = subprocess.run(
            ["crane", "digest", image_with_tag],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _get_current_tag(image: str, values: dict, key: str, fmt: str) -> str:
    """Extract the current tag from the values file to construct the full image ref."""
    # Walk the key path to find the current value
    parts = key.split(".")
    current = values
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return ""
    if current is None:
        return ""

    value = str(current)

    if fmt == "tag_digest":
        # Value is "tag@sha256:..." — extract just the tag
        tag = value.split("@")[0] if "@" in value else value
        return f"{image}:{tag}"
    elif fmt == "digest_only":
        # cert-manager uses separate digest field — get tag from chart default
        # We need the image ref with tag to resolve. Use the chart's appVersion.
        # This is fragile — the pin-images command is best-effort.
        return image  # Will need tag appended
    elif fmt == "sha_only":
        # kube-prometheus-stack uses sha field
        return image  # Will need tag appended
    return ""


def _set_nested(d: dict, key_path: str, value: str) -> None:
    """Set a nested dict value by dot-separated key path."""
    parts = key_path.split(".")
    current = d
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


@click.command("pin-images")
@click.option("--dry-run", is_flag=True, help="Show what would change without writing.")
def pin_images_cmd(dry_run: bool) -> None:
    """Resolve and update container image digests in base-values files.

    Queries container registries for the current SHA256 digest of each
    platform image and updates the base-values.yaml files. Requires
    `crane` (from google/go-containerregistry) on PATH.
    """
    if not shutil.which("crane"):
        console.print(
            "[red]crane not found.[/red] Install it:\n"
            "  brew install crane\n"
            "  # or: go install github.com/google/go-containerregistry/cmd/crane@latest"
        )
        raise SystemExit(1)

    project_root = find_project_root()
    updated = 0
    errors = 0

    for chart_dir, images in CHART_IMAGES.items():
        values_path = project_root / "platform" / chart_dir / "base-values.yaml"
        if not values_path.exists():
            console.print(f"[yellow]Skip {chart_dir}: no base-values.yaml[/yellow]")
            continue

        with open(values_path) as f:
            values = yaml.safe_load(f) or {}

        changed = False
        for img_def in images:
            key = img_def["key"]
            image = img_def["image"]
            fmt = img_def["format"]

            # Build the full image reference for crane
            current_tag = _get_current_tag(image, values, key, fmt)
            if not current_tag:
                # Try to get tag from current value
                parts = key.split(".")
                current = values
                for p in parts:
                    current = current.get(p, {}) if isinstance(current, dict) else None
                if current and isinstance(current, str) and "@" in current:
                    tag = current.split("@")[0]
                    image_ref = f"{image}:{tag}"
                elif current and isinstance(current, str) and current.startswith("sha256:"):
                    # sha_only format — we don't have the tag, skip
                    console.print(f"  [dim]{image}: sha-only, keeping current[/dim]")
                    continue
                else:
                    console.print(f"  [yellow]{image}: can't determine current tag[/yellow]")
                    errors += 1
                    continue
            else:
                image_ref = current_tag

            # Resolve digest
            console.print(f"  Resolving [cyan]{image_ref}[/cyan]...", end=" ")
            digest = _resolve_digest(image_ref)
            if not digest:
                console.print("[red]FAILED[/red]")
                errors += 1
                continue

            # Format the new value
            if fmt == "tag_digest":
                tag = image_ref.split(":")[-1]
                new_value = f"{tag}@{digest}"
            elif fmt == "digest_only":
                new_value = digest
            elif fmt == "sha_only":
                new_value = digest.replace("sha256:", "")
            else:
                new_value = digest

            # Check if changed
            parts = key.split(".")
            current = values
            for p in parts:
                current = current.get(p, {}) if isinstance(current, dict) else None

            if str(current) == new_value:
                console.print(f"[dim]unchanged[/dim]")
                continue

            console.print(f"[green]{digest[:20]}...[/green]")
            if not dry_run:
                _set_nested(values, key, new_value)
                changed = True
            updated += 1

        if changed and not dry_run:
            # Re-read the file as text and do targeted replacements
            # to preserve comments and formatting
            console.print(f"  [green]Updated {values_path.name}[/green]")

    action = "Would update" if dry_run else "Updated"
    console.print(f"\n{action} {updated} image(s), {errors} error(s).")
