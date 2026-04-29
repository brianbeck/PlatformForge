# Platform Services

This directory contains Helm values, overlays, custom rules, and policies for each platform service managed by PlatformForge.

## Structure

Each service follows the same pattern:

```
<service>/
├── base-values.yaml           # Shared Helm values (all environments)
├── overlays/
│   ├── stage/values.yaml      # Stage-specific overrides
│   └── prod/values.yaml       # Prod-specific overrides
└── <service-specific files>   # Rules, constraints, templates, etc.
```

## Services

| Directory | Service | Purpose |
|---|---|---|
| `traefik/` | Traefik | Ingress controller, routes external traffic |
| `observability/` | kube-prometheus-stack | Prometheus, Grafana, Alertmanager, node-exporter |
| `gatekeeper/` | OPA Gatekeeper | Kubernetes admission policy enforcement |
| `falco/` | Falco | Runtime security monitoring via eBPF |
| `trivy-operator/` | Trivy Operator | Continuous vulnerability scanning of running workloads |
| `sealed-secrets/` | Sealed Secrets | Encrypt secrets in Git (default) |
| `external-secrets/` | External Secrets Operator | Sync secrets from external stores (optional) |
| `cert-manager/` | cert-manager | TLS certificate management with Let's Encrypt |
| `argo-rollouts/` | Argo Rollouts | Progressive delivery (blue-green, canary) |

## How values are applied

When `platformforge deploy` is run, the CLI invokes Ansible, which installs Argo CD and generates ApplicationSets. Each ApplicationSet uses Argo CD's multi-source feature to reference:
```
--values base-values.yaml --values overlays/<env>/values.yaml
```

Argo CD owns the Helm release lifecycle — Ansible never runs `helm install` for platform services. Git is the source of truth.

## Making changes

1. Edit the relevant values file
2. Commit and push to Git
3. Argo CD auto-syncs stage; manually sync prod via the Argo CD UI
