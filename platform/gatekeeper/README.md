# OPA Gatekeeper (Policy Enforcement)

Kubernetes admission controller that enforces policies on cluster resources. Uses ConstraintTemplates (policy logic in Rego) and Constraints (policy instances with parameters).

## Files

| File/Directory | Purpose |
|---|---|
| `base-values.yaml` | Shared Helm values: webhook config, audit settings, exempt namespaces |
| `overlays/stage/values.yaml` | Stage: debug logging, smaller resources, fail-open webhook |
| `overlays/prod/values.yaml` | Prod: warn logging, 3 replicas, fail-closed webhook |
| `templates/` | ConstraintTemplates (shared across environments) |
| `constraints/stage/` | Stage Constraints (`dryrun` enforcement) |
| `constraints/prod/` | Prod Constraints (`deny` enforcement) |
| `networkpolicy.yaml` | NetworkPolicy for gatekeeper-system namespace |

## Chart

- **Chart:** `gatekeeper/gatekeeper`
- **Version:** 3.22.0
- **App Version:** v3.22.0

## Deployment architecture

Gatekeeper is deployed as three separate Argo CD Applications to handle CRD ordering:

1. **gatekeeper-core** -- Helm chart install (creates the Gatekeeper controller and webhook)
2. **gatekeeper-templates** -- ConstraintTemplates (creates CRDs for each policy type)
3. **gatekeeper-constraints** -- Constraints (instances that reference the CRDs from step 2)

This ordering is enforced by Ansible during initial deployment and by Argo CD sync-waves for ongoing management.

## ConstraintTemplates

| Template | Kind | What it enforces |
|---|---|---|
| `k8s-block-privileged.yaml` | K8sBlockPrivileged | No privileged containers |
| `k8s-required-labels.yaml` | K8sRequiredLabels | Require `managed-by` and `name` labels |
| `k8s-container-limits.yaml` | K8sContainerLimits | Require CPU and memory limits |
| `k8s-block-latest-tag.yaml` | K8sBlockLatestTag | No `:latest` or untagged images |
| `k8s-block-host-namespace.yaml` | K8sBlockHostNamespace | No hostPID/hostIPC/hostNetwork |
| `k8s-require-nonroot.yaml` | K8sRequireNonRoot | Containers must run as non-root |

## Excluded namespaces

All platform namespaces are excluded from constraints:
`kube-system`, `gatekeeper-system`, `argocd`, `falco`, `falco-stage`, `falco-prod`, `monitoring`, `monitoring-stage`, `monitoring-prod`, `traefik`

This is because platform services have specific security requirements (e.g., Falco needs privileged access for eBPF).

## Adding a new policy

1. Create a ConstraintTemplate in `templates/`:
   ```yaml
   apiVersion: templates.gatekeeper.sh/v1
   kind: ConstraintTemplate
   metadata:
     name: k8syournewpolicy
     annotations:
       argocd.argoproj.io/sync-wave: "1"
   spec:
     crd:
       spec:
         names:
           kind: K8sYourNewPolicy
     targets:
       - target: admission.k8s.gatekeeper.sh
         rego: |
           package k8syournewpolicy
           violation[{"msg": msg}] {
             # your Rego logic
           }
   ```

2. Create Constraints in `constraints/stage/` (dryrun) and `constraints/prod/` (deny)

3. Commit and push -- Argo CD handles the rest

## Checking violations

```bash
# List all constraints and their violation counts
kubectl get constraints -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.totalViolations}{"\n"}{end}'

# Get details for a specific constraint
kubectl get k8sblockprivileged block-privileged-containers -o yaml
```

## Key configuration

- **Webhook failure policy:** `Ignore` for both validating webhooks. This prevents Gatekeeper outages from blocking the entire cluster.
- **Exempt namespaces:** `kube-system`, `gatekeeper-system`, `argocd` are exempt at the Gatekeeper controller level (in addition to per-constraint exclusions).
- **Audit interval:** 60s (base), 30s (stage), 120s (prod).
