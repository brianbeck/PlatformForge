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
**Trigger: implement before DevExForge deploys to prod.** Currently low risk —
`platformforge deploy` rebuilds everything from Git + vault. Once DevExForge
creates Argo CD Applications dynamically (team apps, repo credentials, custom
RBAC), Argo CD holds state that no single Git repo can reconstruct.
Plan:
- CronJob: `argocd admin export` daily → upload to MinIO (on the local network)
- MinIO endpoint, bucket, credentials prompted during `platformforge init` (optional)
- `platformforge backup` / `platformforge restore` CLI commands
- Runbook in README: full recovery procedure (scratch rebuild vs partial restore)
- Credentials stored in Ansible Vault

**7. Pod Disruption Budgets** (was #6) — **DONE**
PDBs with `maxUnavailable: 1` added for Traefik (prod), Argo CD server + controller,
and Argo Rollouts controller + dashboard (prod).

**8. Resource quotas / LimitRange for team namespaces** (was #7)
DevExForge creates team namespaces dynamically. Without ResourceQuotas, a single team can starve the cluster. PlatformForge could provide a default LimitRange via Gatekeeper or a shared Helm chart that DevExForge applies on namespace creation.

**9. Log aggregation** (was #8) — **DONE**
Grafana Alloy (wave 22) ships container logs to external Loki. Loki URL configured
via `platformforge init`, Alloy deployed as DaemonSet on both clusters. Loki added
as Grafana datasource in the in-cluster Grafana instances.

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

**ClusterForge: control plane metrics Services**
etcd, kube-controller-manager, and kube-scheduler run as static pods but lack headless
Services for Prometheus discovery. Create Services in ClusterForge exposing metrics ports
(etcd: 2381, controller-manager: 10257, scheduler: 10259), then re-enable monitoring in
`platform/observability/base-values.yaml` (`kubeEtcd`, `kubeControllerManager`, `kubeScheduler`).

**Email notification provider: multi-recipient routing**
The email provider currently sends all alerts to a single address. To match the Slack
experience, add per-severity and per-type routing:
- Separate "to" addresses for critical vs warning
- Separate addresses for security (Falco) and vulnerability (Trivy) alerts
- Per-environment subject line prefixes (`[STAGE]` vs `[PROD]`)
- CLI wizard should prompt for each recipient with the same contextual descriptions
  used by the Slack channel prompts

**Generic webhook notification provider**
Add a third notification provider option (`webhook`) to `platformforge init` alongside Slack and Email.
Configures Argo CD `service.webhook.generic` and Alertmanager `webhook_configs` receiver with a user-provided URL.

**Team-scoped alert routing**
As DevExForge onboards teams, each team may want alerts for their own namespaces routed
to their own Slack channels or email addresses. This would require:
- A configurable alert routing table (team → namespace pattern → destination)
- Either a CLI command (`platformforge alerts add-route`) or a declarative config file
  that maps team namespaces to notification channels
- Alertmanager route hierarchy: platform-wide routes (current) as the default,
  with team-specific sub-routes that match by namespace label
- Argo CD notification subscriptions per-Application (already supported via annotations)
- Consider whether this belongs in PlatformForge (platform team controls routing) or
  DevExForge (teams self-service their own alert destinations)

**Centralized observability: single pane of glass**
Currently the observability stack is split across three places:
- **In-cluster Grafana** (stage + prod): metrics dashboards (Prometheus datasource), 
  Grafana.com provisioned dashboards (ArgoCD, Falco, Trivy, Node Exporter)
- **External Grafana**: log searching (Loki datasource via Alloy)
- **In-cluster Alertmanager**: alert routing to Slack

To get a single pane of glass in the external Grafana, add:
1. **Remote Prometheus datasources**: Add each cluster's Prometheus as a datasource 
   in the external Grafana (`http://<prometheus-service>:9090`). Requires network 
   reachability from the external Grafana host to the cluster Traefik LoadBalancer IPs.
   Could also use the Prometheus HTTPRoutes (`https://prometheus-{stage,prod}.<domain>`).
2. **Remote Alertmanager datasource**: Same pattern — point external Grafana at the 
   in-cluster Alertmanager endpoints.
3. **Prometheus remote-write to Mimir/Thanos**: For long-term metric storage and 
   cross-cluster queries. Requires deploying Mimir or Thanos externally (like Loki).
   This is the enterprise approach for multi-cluster metric aggregation.

**Recommended dashboard IDs for external Grafana (Loki logs):**
- Loki Kubernetes Logs (ID 15141): browse logs by namespace, pod, container

**Cloud portability (AWS EKS / GCP GKE)**
PlatformForge is ~90% cloud-portable today. All platform services, ApplicationSets,
CLI, and CI work unchanged. The env repo (`platformforge-env`) absorbs cloud-specific
config via overlay values. Changes needed for full cloud support:

1. **DNS registration** — the `pihole_dns` role is homelab-specific. For cloud:
   - Add `external-dns` as a new platform service (Helm chart, wave 12 after Traefik)
   - `external-dns` auto-creates Route53/Cloud DNS records from HTTPRoutes/Gateway
   - Add `dns_provider` choice to `platformforge init`: `pihole`, `external-dns`, `none`
   - Pi-hole role becomes one option, not the default

2. **Gateway provider** — currently hardcoded to `GatewayClass: traefik`. For cloud:
   - Make `gatewayClassName` configurable in `platformforge init`
   - AWS: `amazon-vpc-lattice` or keep Traefik
   - GKE: `gke-l7-global-external-managed` or keep Traefik
   - Template the Gateway resource with `{{ gateway_class_name }}`

3. **Storage** — prod overlays disable persistence due to `local-path` limitations:
   - Cloud StorageClasses (gp3, pd-standard) support ReadWriteOnce properly
   - Cloud env repo overlays should enable Prometheus/Grafana persistence
   - Add `storage_class` to `platformforge init` (default: cluster default)

4. **Secrets strategy** — Sealed Secrets works everywhere but cloud-native is better:
   - AWS: External Secrets Operator + AWS Secrets Manager (already supported)
   - GCP: External Secrets Operator + GCP Secret Manager (already supported)
   - The `secrets_strategy` choice in `platformforge init` already handles this

5. **TLS certificates** — cert-manager works on all clouds:
   - AWS: cert-manager + Route53 DNS-01 solver (same pattern as Cloudflare)
   - GCP: cert-manager + Cloud DNS solver
   - Or use cloud-native certs (ACM, Google-managed) — would need a new cert provider option
   - The `cloudflare_api_token` vault key would need to generalize to `dns_solver_credentials`

6. **LoadBalancer** — no PlatformForge change needed:
   - Cloud clusters auto-provision NLB/ALB/GCP LB for `type: LoadBalancer` services
   - MetalLB is only needed on bare metal (ClusterForge responsibility, not PlatformForge)

**What works immediately on cloud (no changes):**
- All platform services (Argo CD, Gatekeeper, Falco, Trivy, Argo Rollouts, Alloy)
- ApplicationSets (use `kubernetes.default.svc`)
- CLI (`platformforge scaffold/init/deploy/status/teardown`)
- CI pipeline
- Two-repo model (PlatformForge public + env repo private)
- Multi-channel Slack alerting
- Grafana dashboards
- Pod Disruption Budgets
- Gateway API (if using Traefik on cloud)

**Estimated scope:** 2-3 days for DNS provider abstraction + GatewayClass config.
The rest is env-repo-level config, not PlatformForge code changes.

**Security Layer 4: Gatekeeper + External Data Provider** — **DONE**
Trivy admission provider (Go) queries VulnerabilityReport CRDs at admission time.
K8sBlockCriticalCVE ConstraintTemplate enforces thresholds:
- Stage: maxCritical=0, maxHigh=10 (dryrun)
- Prod: maxCritical=0, maxHigh=5 (deny)

**CVE policy audit trail + DevExForge integration**
When teams need to modify CVE thresholds (exemptions, temporary increases):
- Changes to constraint parameters should be tracked with:
  - Who requested the change
  - Business justification (which CVE, which image, why)
  - Remediation date (when the exemption expires)
  - Approval (who approved the risk acceptance)
- DevExForge should provide a self-service UI/CLI for teams to:
  - Request CVE exemptions for their namespaces
  - View current violations and remediation status
  - Auto-expire exemptions after the agreed date
- Implementation options:
  - Custom CRD (`CVEExemption`) with approval workflow (DevExForge operator reconciles)
  - Git-based: teams submit PRs to env repo constraints with exemption template
  - Audit log: all constraint changes logged to Loki with requester/approver metadata
- This ties into the broader HIPAA audit controls requirement (§164.312(b))

## HIPAA Compliance Readiness

PlatformForge is designed to support healthcare (HIPAA-compliant) workloads. This section
tracks alignment with HIPAA Technical Safeguards (45 CFR §164.312).

### Current Status

| HIPAA Requirement | Section | Status | PlatformForge Implementation |
|---|---|---|---|
| **Access Control** | §164.312(a) | Partial | Argo CD RBAC (role:platform-admin), Gatekeeper admission policies, Keycloak available for SSO |
| **Audit Controls** | §164.312(b) | Partial | Falco runtime detection, Alloy log shipping to Loki, Argo CD operation history |
| **Integrity Controls** | §164.312(c) | Mostly Done | 27 images digest-pinned, Sigstore policy-controller deployed, Gatekeeper K8sRequireImageDigest enforced in team namespaces |
| **Transmission Security** | §164.312(e) | Done | TLS everywhere via cert-manager + Gateway API, HTTPS-only entrypoints |
| **Encryption at Rest** | §164.312(a)(2)(iv) | Partial | Sealed Secrets for K8s secrets, Ansible Vault for config secrets |
| **Network Segmentation** | — | Partial | NetworkPolicies for Falco + Gatekeeper namespaces |
| **Vulnerability Management** | — | Done | Trivy Operator continuous scanning + PrometheusRules + Slack alerting |
| **Incident Detection** | — | Done | Falco eBPF runtime detection + multi-channel Slack alerting |
| **Backup & Recovery** | — | TODO | Argo CD backup planned (trigger: before DevExForge prod) |

### Remaining HIPAA Work

**Access Control:**
- OIDC/SSO integration for all dashboards (Argo CD, Grafana, Alertmanager, Rollouts)
- Service-to-service mTLS (Linkerd or Istio service mesh, or Traefik's built-in mTLS)
- RBAC audit: document who has access to what and why

**Audit Controls:**
- Audit log retention policy (how long logs are kept in Loki, minimum 6 years for HIPAA)
- Kubernetes API audit logging enabled and shipped to Loki
- Immutable audit trail (write-once storage for compliance evidence)

**Encryption at Rest:**
- etcd encryption at rest (ClusterForge responsibility — enable `--encryption-provider-config`)
- PersistentVolume encryption (cloud: encrypted EBS/PD by default; homelab: LUKS on nodes)
- Backup encryption (MinIO server-side encryption for Argo CD exports)

**Network Segmentation:**
- NetworkPolicies for ALL platform namespaces (#11 on roadmap) — currently only Falco + Gatekeeper
- Microsegmentation for team namespaces (default-deny + per-service allow)
- Egress controls (restrict which services can reach the internet)

**Integrity Controls:**
- ~~Image digest pinning for all platform images~~ — **DONE** (27 images)
- ~~Sigstore policy-controller for signature verification~~ — **DONE** (wave 32)
- ~~Gatekeeper K8sRequireImageDigest ConstraintTemplate~~ — **DONE** (dryrun stage, deny prod)
- `platformforge pin-images` CLI command for refreshing digests on upgrades — **DONE**
- Security Layer 4: Gatekeeper + Trivy admission-time CVE blocking — TODO

**Backup & Recovery:**
- Argo CD state backup to MinIO (#6 on roadmap)
- Application data backup strategy (per-team responsibility, PlatformForge provides Velero or similar)
- Disaster recovery runbook with Recovery Time Objective (RTO) and Recovery Point Objective (RPO)

**Compliance Documentation:**
- Business Associate Agreement (BAA) template for cloud providers
- Security controls mapping document (HIPAA safeguard → PlatformForge implementation)
- Penetration testing schedule and scope
- Incident response playbook
