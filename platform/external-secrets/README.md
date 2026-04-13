# External Secrets Operator

Syncs secrets from external stores into Kubernetes Secrets. Supports HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, 1Password, and more.

## Chart

- **Chart:** `external-secrets/external-secrets`
- **Version:** 2.3.0
- **App Version:** v2.3.0

## Prerequisites

An external secret store must be running and accessible from the cluster. Common options:
- HashiCorp Vault (self-hosted or HCP)
- AWS Secrets Manager
- 1Password Connect

## Configuration

After ESO is deployed, you need to create:

1. **ClusterSecretStore** -- points to your external store
2. **ExternalSecret** -- defines which secret to sync and where

### Example: HashiCorp Vault

```yaml
# ClusterSecretStore
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"

---
# ExternalSecret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-secret
  namespace: default
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/myapp
        property: password
```

## When to use ESO vs Sealed Secrets

| | Sealed Secrets | External Secrets |
|---|---|---|
| External infrastructure | None needed | Vault/cloud provider required |
| Secret rotation | Manual (re-seal) | Automatic (refreshInterval) |
| Audit trail | Git history | External store audit log |
| Multi-cluster | Each cluster has own key | Shared external store |
| Best for | Homelab, small teams | Enterprise, compliance |
