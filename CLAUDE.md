# CLAUDE.md - PlatformForge Project Guide

## Project Overview

PlatformForge is a GitOps-oriented platform services management system for Kubernetes. It uses Ansible for initial deployment and Argo CD for ongoing declarative management. Designed to work alongside ClusterForge (which provisions Kubernetes clusters on Proxmox).

## Architecture

- **Ansible** installs all services via Helm in dependency order
- **Argo CD** takes over for GitOps management after initial install
- **Two environment models:** Model A (single cluster, namespace separation) and Model B (separate clusters)

## Deployment Order

```
1. Traefik (ingress)
2. Observability (Prometheus, Grafana, Alertmanager)
3. DevSecOps (Gatekeeper + Falco)
4. Vulnerability Scanning (Trivy Operator)
5. Argo CD (registers all apps)
6. DNS (Pi-hole registration)
```

## Key Directories

- `ansible/playbooks/` - All deployment, teardown, and health check playbooks
- `ansible/roles/` - Discovery roles and Argo CD templates
- `platform/` - Helm values and overlays for each service
- `argocd/` - Generated Argo CD manifests (committed after bootstrap)

## Services and Versions

| Service | Chart | Version | Namespace |
|---|---|---|---|
| Traefik | traefik/traefik | 39.0.7 | traefik |
| kube-prometheus-stack | prometheus-community/kube-prometheus-stack | 82.15.1 | monitoring / monitoring-{stage,prod} |
| OPA Gatekeeper | gatekeeper/gatekeeper | 3.22.0 | gatekeeper-system |
| Falco | falcosecurity/falco | 8.0.1 | falco / falco-{stage,prod} |
| Trivy Operator | aquasecurity/trivy-operator | 0.32.1 | trivy-system |
| Argo CD | argo/argo-cd | 9.4.17 | argocd |

## Security Layer Model

| Layer | Tool | When | Action | Status |
|---|---|---|---|---|
| 1 | Trivy CLI (in CI/CD pipeline) | Build time | Fail build on critical CVEs | User implements in CI |
| 2 | Trivy Operator + Prometheus | Runtime | Alert on CVEs in running images | Implemented |
| 3 | Trivy Operator + Prometheus | Continuous | Alert when new CVEs affect deployed images | Implemented |
| 4 | Gatekeeper + External Data Provider | Deploy time | Block images with CVEs at admission | **NOT YET IMPLEMENTED** |

### Layer 4 Implementation Notes (Future)

Layer 4 would use Gatekeeper's External Data Provider to query Trivy Operator's vulnerability data at admission time. When a pod is created, Gatekeeper would check if the image has too many CVEs and reject it.

Required components:
- Gatekeeper External Data Provider CRD pointing to Trivy Operator
- A ConstraintTemplate that queries vulnerability data via the provider
- Constraints with configurable CVE thresholds (e.g., deny if CRITICAL > 0)

Reference: https://open-policy-agent.github.io/gatekeeper/website/docs/externaldata

## Important Patterns

### Model A vs Model B

- **Cluster-scoped singletons** (Traefik, Argo CD, Gatekeeper core): install once, guarded by `when: multi_cluster | bool`
- **Namespace-scoped services** (Falco, Observability, Trivy Operator): always install for both stage and prod

### Traefik IngressRoutes

Use Traefik IngressRoute CRDs instead of standard Kubernetes Ingress. Traefik v3 forces HTTPS backend connections on the `websecure` entrypoint with standard Ingress. IngressRoutes allow `scheme: http` on backends.

### Gatekeeper Constraints

- Platform namespaces are excluded from all constraints
- Stage uses `dryrun` enforcement; prod uses `deny`
- Constraints are cluster-scoped with the same names in stage/prod, so in Model A only stage constraints are applied

### Helm Values Layering

Every service: `base-values.yaml` + `overlays/{env}/values.yaml`
Argo CD Applications use multi-source to reference these from Git.

## Common Issues

- **Gatekeeper webhook blocks namespace creation:** Clean up with `kubectl delete validatingwebhookconfiguration -l gatekeeper.sh/system=yes`
- **kube-prometheus-stack stuck on install:** Delete orphaned jobs and Helm secrets in the monitoring namespace
- **Falco can't download artifacts:** Ensure NetworkPolicy allows HTTPS egress (port 443)
- **Argo CD shows Unknown sync:** Push generated manifests to Git

## Configuration

- `environments.yml` - All bootstrap configuration (gitignored)
- `ansible/vault/secrets.yml` - Pi-hole credentials (Ansible Vault encrypted)
- `ansible/group_vars/all.yml` - Default variables
