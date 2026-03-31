# Trivy Operator (Vulnerability Scanning)

Continuously scans all running workloads for vulnerabilities, misconfigurations, exposed secrets, and RBAC issues. Results are stored as Kubernetes CRDs and exposed as Prometheus metrics for alerting.

## Security Layer Model

Trivy Operator provides **Layer 2** and **Layer 3** of the vulnerability defense model:

| Layer | Tool | When | Action |
|---|---|---|---|
| 1 | Trivy CLI (in CI) | Build time | Fail build on critical CVEs |
| **2** | **Trivy Operator + Prometheus** | **Runtime** | **Alert on CVEs in running images** |
| **3** | **Trivy Operator + Prometheus** | **Continuous** | **Alert when new CVEs affect deployed images** |
| 4 | Gatekeeper + External Data | Deploy time | Block images with CVEs at admission (planned) |

## Files

| File | Purpose |
|---|---|
| `base-values.yaml` | Shared Helm values: scan config, intervals, ServiceMonitor |
| `overlays/stage/values.yaml` | Stage: 12h rescan interval, smaller resources |
| `overlays/prod/values.yaml` | Prod: 24h rescan interval, larger resources |
| `prometheusrules.yaml` | Alerting rules for critical CVEs, high counts, operator health |

## Chart

- **Chart:** `aquasecurity/trivy-operator`
- **Version:** 0.32.1
- **App Version:** 0.30.1

## What it scans

- **Vulnerability scanning:** CVEs in OS packages and language dependencies
- **Config audit:** Kubernetes resource misconfigurations
- **RBAC assessment:** Over-permissive roles and bindings
- **Exposed secrets:** Secrets accidentally included in images

## Viewing results

```bash
# List vulnerability reports
kubectl get vulnerabilityreports -A

# Get details for a specific image
kubectl get vulnerabilityreports -n <namespace> -o yaml

# Summary of critical/high CVEs across all images
kubectl get vulnerabilityreports -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.report.artifact.repository}:{.report.artifact.tag}{"\t"}Critical:{.report.summary.criticalCount} High:{.report.summary.highCount}{"\n"}{end}'
```

## Prometheus alerts

| Alert | Severity | Condition |
|---|---|---|
| CriticalVulnerabilityDetected | critical | Any image has CRITICAL CVEs |
| HighVulnerabilityThresholdExceeded | warning | Any image has >10 HIGH CVEs |
| ClusterVulnerabilityCountHigh | warning | Total critical+high > 50 across cluster |
| TrivyOperatorNotScanning | warning | No vulnerability data for 2+ hours |
| CriticalMisconfigurationDetected | warning | Critical K8s misconfigurations found |

## Excluded namespaces

Platform namespaces are excluded from scanning by default since they're managed by PlatformForge: `kube-system`, `kube-node-lease`, `kube-public`, `argocd`, `gatekeeper-system`, `trivy-system`

## Future: Layer 4 (Gatekeeper External Data)

> **Not yet implemented.** This is the planned next step.

Gatekeeper can query Trivy Operator's vulnerability data at admission time using the External Data Provider. When a pod is created, Gatekeeper checks if the image has too many CVEs and rejects it if it exceeds a threshold.

This would add deploy-time blocking in addition to the runtime alerting that's already in place.
