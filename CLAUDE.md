# CLAUDE.md - PlatformForge Project Guide

## Project Overview

PlatformForge is a GitOps platform services management system for Kubernetes. Ansible bootstraps Argo CD; Argo CD owns and deploys all platform services via ApplicationSets. Designed to work alongside ClusterForge (cluster provisioning) and DevExForge (developer experience).

## Architecture

**Single-owner model:** Ansible installs Argo CD. Argo CD installs everything else.

**No dual control:** Ansible never runs `helm install` for platform services. This eliminates drift between Ansible's Helm rendering and Argo CD's Helm rendering.

## Deployment Order (Sync Waves)

```
Wave -10  Sealed Secrets or External Secrets Operator
Wave 10   Traefik (ingress controller)
Wave 20   kube-prometheus-stack (monitoring CRDs + stack)
Wave 30   Gatekeeper controller
Wave 40   Gatekeeper ConstraintTemplates (creates CRDs)
Wave 50   Gatekeeper Constraints (uses CRDs from wave 40)
Wave 60   Falco (runtime security)
Wave 70   Trivy Operator (vulnerability scanning)
Wave 80   Argo Rollouts (progressive delivery)
```

### Argo Rollouts: Traffic Routing Status

Currently deployed **without a traffic-router plugin**. Supported strategies:
- `blueGreen` — service-selector swap (no weighting). Fully functional.
- `canary` — replica-based, relies on Service round-robin. No precise traffic split.

**TODO (Phase 2):** Add real weighted traffic shifting. The historical
`argoproj-labs/traefik` plugin was never released, and the official Argo
Rollouts docs now route Traefik users through the Gateway API plugin
(`argoproj-labs/gatewayAPI`,
`https://github.com/argoproj-labs/rollouts-plugin-trafficrouter-gatewayapi`).
This requires:

1. Migrating Traefik from `IngressRoute` CRDs to Kubernetes Gateway API
   resources (`Gateway`, `HTTPRoute`). Traefik 3.x ships a Gateway API
   provider that needs to be enabled in `platform/traefik/base-values.yaml`.
2. Rewriting all PlatformForge IngressRoutes (Argo CD, Grafana,
   Prometheus, Argo Rollouts dashboard) as `HTTPRoute` resources, or
   running both providers side-by-side during transition.
3. Adding the Gateway API plugin to `platform/argo-rollouts/base-values.yaml`
   under `controller.trafficRouterPlugins` (the value is a list — see
   commit history for the correct structure).
4. Updating `platform/argo-rollouts/rbac/` with a ClusterRole granting
   the controller patch access to `gateway.networking.k8s.io/httproutes`.

Estimated scope: 1-2 days of work, touches Traefik values and every
existing IngressRoute in the repo.

## Key Directories

- `ansible/playbooks/` - bootstrap, install-argocd, healthcheck, teardown
- `ansible/roles/argocd_install/` - Argo CD Helm install + ApplicationSet templates
- `argocd/root/` - AppProjects (generated)
- `argocd/waves/` - ApplicationSets grouped by sync wave (generated)
- `platform/` - Helm values and overlays for each service

## Services and Versions

| Service | Chart | Version | Namespace |
|---|---|---|---|
| Traefik | traefik/traefik | 39.0.7 | traefik |
| kube-prometheus-stack | prometheus-community/kube-prometheus-stack | 82.15.1 | monitoring / monitoring-{stage,prod} |
| OPA Gatekeeper | gatekeeper/gatekeeper | 3.22.0 | gatekeeper-system |
| Falco | falcosecurity/falco | 8.0.1 | falco / falco-{stage,prod} |
| Trivy Operator | aquasecurity/trivy-operator | 0.32.1 | trivy-system |
| Sealed Secrets | sealed-secrets/sealed-secrets | 2.18.5 | sealed-secrets |
| External Secrets (optional) | external-secrets/external-secrets | 2.3.0 | external-secrets |
| Argo CD | argo/argo-cd | 9.4.17 | argocd |
| Argo Rollouts | argo/argo-rollouts | 2.40.9 | argo-rollouts |

## Environment Models

**Model A (single cluster):**
- `single_cluster = true`, `stage_context == prod_context`
- Singletons (Traefik, Gatekeeper, Trivy): one instance
- Namespace-scoped (Falco, Observability): two instances in different namespaces
- One Argo CD with ApplicationSets generating both stage and prod apps

**Model B (two clusters):**
- `multi_cluster = true`, `stage_context != prod_context`
- Each cluster has its own Argo CD
- Same ApplicationSets applied to each Argo CD
- Each Argo CD manages only its own cluster

## ApplicationSet Categories

- **Singleton services:** Generator has one entry per Argo CD instance (Traefik, Gatekeeper, Trivy)
- **Namespace-scoped services:** Generator has entries for each environment (Falco, Observability)
- **Constraint services:** Generator has one entry in Model A (stage/dryrun only), one per cluster in Model B

## Security Layer Model

| Layer | Tool | When | Status |
|---|---|---|---|
| 1 | Trivy CLI (in CI/CD) | Build time | User implements in CI |
| 2 | Trivy Operator + Prometheus | Runtime | **Implemented** |
| 3 | Trivy Operator + Prometheus | Continuous | **Implemented** |
| 4 | Gatekeeper + External Data Provider | Deploy time | **NOT YET IMPLEMENTED** |

### Layer 4 Implementation Notes (Future)

Gatekeeper External Data Provider querying Trivy Operator vulnerability data at admission time.

Required components:
- Gatekeeper External Data Provider CRD pointing to Trivy Operator
- ConstraintTemplate querying vulnerability data via the provider
- Constraints with configurable CVE thresholds

Reference: https://open-policy-agent.github.io/gatekeeper/website/docs/externaldata

## Common Issues

- **Gatekeeper webhook blocks namespace creation:** Keep `validatingWebhookCheckIgnoreFailurePolicy: Ignore` in values
- **Falco can't download artifacts:** Ensure NetworkPolicy allows HTTPS egress (port 443)
- **Argo CD shows Unknown sync:** Push generated ApplicationSets to Git
- **kube-prometheus-stack webhook caBundle drift:** Handled by `ignoreDifferences` in ApplicationSet

## Playbook Reference

```bash
cd ansible
ansible-playbook playbooks/bootstrap.yml        # Configure (interactive)
ansible-playbook playbooks/install-argocd.yml    # Install Argo CD + deploy platform
ansible-playbook playbooks/healthcheck.yml       # Verify all services
ansible-playbook playbooks/teardown.yml          # Clean removal
ansible-playbook playbooks/deploy-dns.yml        # Re-register Pi-hole DNS
```
