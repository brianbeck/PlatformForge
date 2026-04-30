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

### Gateway API and Argo Rollouts Traffic Routing

Traefik uses the **Gateway API provider** (`kubernetesGateway`). All service
routing uses `HTTPRoute` resources referencing a cluster-level `Gateway` in
the `traefik` namespace. IngressRoute CRDs (`kubernetesCRD` provider) are
**disabled**.

Argo Rollouts loads the `argoproj-labs/gatewayAPI` traffic-router plugin
(v0.13.0) at controller startup. This plugin manipulates HTTPRoute
`backendRef` weights to shift traffic between stable and canary services
during canary rollout steps.

**Key resources:**
- Gateway API CRDs: v1.4.0 (installed by `install-argocd.yml` before ApplicationSets)
- GatewayClass: `traefik` (auto-created by Traefik when provider is enabled)
- Gateway: `traefik/traefik` (templated by Ansible, applied after Traefik deploys)
- Plugin: `argoproj-labs/gatewayAPI` v0.13.0 in `platform/argo-rollouts/base-values.yaml`
- RBAC: `platform/argo-rollouts/rbac/gateway-rbac.yaml` grants the controller HTTPRoute access

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

## CLI Reference

```bash
pip install -e .                         # Install CLI (editable)
platformforge init                       # Interactive bootstrap wizard
platformforge deploy                     # Install Argo CD + deploy platform
platformforge status                     # Verify all services
platformforge teardown                   # Clean removal (--yes to skip prompt)
platformforge dns                        # Re-register Pi-hole DNS
platformforge config show                # Display current config
platformforge config set KEY VALUE       # Modify a single config value
```

The CLI writes `environments.yml` and `ansible/vault/secrets.yml`; Ansible playbooks
read them.  Ansible playbooks remain functional for direct use under `ansible/playbooks/`.

Source: `src/platformforge/` (Click + Rich + Pydantic).  Install with `pip install -e ".[dev]"` for tests.

## Production Readiness Roadmap

### High Priority

**1. CI pipeline for PlatformForge itself** — **DONE**
GitHub Actions workflow with yaml-lint, helm-template (18 matrix jobs), gatekeeper-test, and python-tests.

**2. Argo CD notifications** — **DONE**
Configured via `platformforge init` (Slack or Email). Templates, triggers, and subscriptions
are wired in `values.yml.j2`. Webhook URL stored in Ansible Vault.
Future TODO: add generic webhook support.

**3. Alertmanager routing** — **DONE**
Alertmanager receiver config templated per-env (`alertmanager-values.yaml`) from the
notification provider chosen in `platformforge init`. Slack/Email routes critical alerts.
12 PrometheusRules (Falco + Trivy) fire to the configured receiver.

**4. Grafana dashboards-as-code** — **DONE**
Dashboards provisioned via Grafana.com IDs in `platform/observability/dashboards/dashboards-values.yaml`:
- Argo CD (ID 14584), Falco (ID 11914), Trivy Operator (ID 16337), Node Exporter (ID 1860)
- Default Kubernetes dashboards enabled via `defaultDashboardsEnabled: true` (chart default)

### Medium Priority

**5. Branch protection + PR-based workflow**
Currently pushes to `main` trigger Argo CD reconciliation before CI finishes. Set up:
- GitHub branch protection on `main` requiring CI to pass before merge
- PR-based workflow (no direct pushes to `main`)
- Optionally disable Argo CD auto-sync on prod and require manual sync after stage is verified

**6. Backup/restore for Argo CD** (was #5)
If the Argo CD namespace is deleted, all Application state, RBAC, repo credentials are lost. Options: `argocd admin export` via CronJob to PV or S3. Since ApplicationSets are in Git, the main risk is custom RBAC and repo configs — at minimum document the manual restore path.

**7. Pod Disruption Budgets** (was #6)
Prod overlays set 2 replicas for Traefik, observability, and argo-rollouts but no PDBs. A node drain can take both replicas simultaneously. Add PDBs for:
- Traefik (`maxUnavailable: 1`)
- Argo CD server + controller
- Argo Rollouts controller (prod)

**8. Resource quotas / LimitRange for team namespaces** (was #7)
DevExForge creates team namespaces dynamically. Without ResourceQuotas, a single team can starve the cluster. PlatformForge could provide a default LimitRange via Gatekeeper or a shared Helm chart that DevExForge applies on namespace creation.

**9. Log aggregation** (was #8)
Metrics (Prometheus) and runtime detection (Falco) exist, but no centralized logging. Options:
- Loki + Promtail (lightweight, fits the Grafana ecosystem already deployed)
- Document that ClusterForge clusters ship logs to an external system
Without this, debugging a crash-looping pod means `kubectl logs` on the right node at the right time.

**10. Sealed Secrets key rotation** (was #9)
Sealed Secrets controller generates an encryption key on first install. If the controller is reinstalled, existing SealedSecrets become undecryptable. Add a CronJob or documented procedure to:
- Back up the encryption key
- Rotate periodically

### Lower Priority

**11. Network policies for all services** (was #10)
Network policies exist for Falco and Gatekeeper, but not for: Traefik, observability stack, cert-manager, sealed-secrets, argo-rollouts, Argo CD. A "default-deny + explicit allow" model for every platform namespace would harden the blast radius of a compromised pod.

**12. Automated testing for Gatekeeper policies** (was #11)
Six ConstraintTemplates exist but no `gator test` suite validates them against sample resources. A passing constraint test could silently break after a Gatekeeper upgrade.

**13. Image pinning / signature verification** (was #12)
All Helm charts reference upstream container images by tag, not digest. A supply chain attack on a chart's image tag would propagate through Argo CD auto-sync. Consider:
- Cosign signature verification (if available for upstream images)
- Digest pinning for prod overlays

**14. Runbooks** (was #13)
README troubleshooting section covers 4 scenarios. Production runbooks should cover: certificate expiry, sealed-secrets key loss, Argo CD admin password reset, node failure impact, and the full disaster recovery procedure (rebuild from scratch using only Git + vault password).

### Existing TODOs

**Generic webhook notification provider**
Add a third notification provider option (`webhook`) to `platformforge init` alongside Slack and Email.
Configures Argo CD `service.webhook.generic` and Alertmanager `webhook_configs` receiver with a user-provided URL.

**Security Layer 4: Gatekeeper + External Data Provider**
Gatekeeper querying Trivy Operator vulnerability data at admission time. Required components:
- Gatekeeper External Data Provider CRD pointing to Trivy Operator
- ConstraintTemplate querying vulnerability data via the provider
- Constraints with configurable CVE thresholds
Reference: https://open-policy-agent.github.io/gatekeeper/website/docs/externaldata
