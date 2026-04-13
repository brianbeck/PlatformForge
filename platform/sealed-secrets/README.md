# Sealed Secrets

Encrypts Kubernetes Secrets so they can be safely stored in Git. The Sealed Secrets controller running in the cluster is the only component that can decrypt them.

## How it works

```
Developer                          Cluster
   │                                  │
   ├── kubeseal encrypt ──────────>   │
   │   (uses controller's public key) │
   │                                  │
   ├── SealedSecret YAML ──> Git ──>  Argo CD
   │   (encrypted, safe to commit)    │
   │                                  ├── Sealed Secrets Controller
   │                                  │   (decrypts with private key)
   │                                  │
   │                                  └── Kubernetes Secret
   │                                      (available to pods)
```

## Chart

- **Chart:** `sealed-secrets/sealed-secrets`
- **Version:** 2.18.5
- **App Version:** 0.36.6

## Creating a SealedSecret

### 1. Install kubeseal CLI

```bash
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/kubeseal-linux-amd64 -O kubeseal
chmod +x kubeseal && sudo mv kubeseal /usr/local/bin/
```

### 2. Create a regular Secret

```bash
kubectl create secret generic my-secret \
  --from-literal=username=admin \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml > my-secret.yaml
```

### 3. Encrypt it

```bash
# For stage cluster
kubeseal --controller-name=sealed-secrets-controller \
  --controller-namespace=sealed-secrets \
  --context beck-stage-admin@beck-stage \
  --format yaml < my-secret.yaml > my-sealed-secret.yaml

# For prod cluster
kubeseal --controller-name=sealed-secrets-controller \
  --controller-namespace=sealed-secrets \
  --context beck-prod-admin@beck-prod \
  --format yaml < my-secret.yaml > my-sealed-secret-prod.yaml
```

### 4. Commit the SealedSecret

```bash
# Safe to commit -- only the controller can decrypt
git add my-sealed-secret.yaml
git commit -m "Add encrypted secret"
git push
```

### 5. Apply or let Argo CD sync

The SealedSecret is applied to the cluster. The controller decrypts it and creates a regular Kubernetes Secret.

## Important notes

- Each cluster has its own encryption key pair. Secrets sealed for stage **cannot** be unsealed on prod.
- Back up the controller's private key: `kubectl get secret -n sealed-secrets -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > sealed-secrets-key-backup.yaml`
- Store the backup securely outside the cluster.
- If you lose the private key, you cannot decrypt existing SealedSecrets.
