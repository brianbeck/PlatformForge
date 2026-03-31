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

## How values are applied

During initial deployment, Ansible runs `helm upgrade --install` with:
```
--values base-values.yaml --values overlays/<env>/values.yaml
```

After deployment, Argo CD Applications reference the same files via multi-source, keeping Git as the source of truth.

## Making changes

1. Edit the relevant values file
2. Commit and push to Git
3. Argo CD auto-syncs stage; manually sync prod via the Argo CD UI
