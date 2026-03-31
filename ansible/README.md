# Ansible

Ansible playbooks and roles for deploying and managing PlatformForge platform services.

## Playbooks

| Playbook | Purpose | Interactive? |
|---|---|---|
| `bootstrap.yml` | Configure environment (prompts for all settings) | Yes |
| `deploy-all.yml` | Deploy everything in the correct order | No |
| `deploy-ingress.yml` | Deploy Traefik ingress controller | No |
| `deploy-observability.yml` | Deploy Prometheus, Grafana, Alertmanager | No |
| `deploy-devsecops.yml` | Deploy OPA Gatekeeper + Falco | No |
| `deploy-continuousdeployment.yml` | Deploy Argo CD, register all Applications | No |
| `deploy-dns.yml` | Register hostnames with Pi-hole DNS | No |
| `healthcheck.yml` | Verify all services across all clusters | No |
| `teardown.yml` | Clean removal of all services | Yes (confirmation) |

### Typical workflow

```bash
cd ansible

# First time: configure everything
ansible-playbook playbooks/bootstrap.yml

# Deploy all services
ansible-playbook playbooks/deploy-all.yml

# Check health
ansible-playbook playbooks/healthcheck.yml

# Tear down when needed
ansible-playbook playbooks/teardown.yml
```

### Re-running playbooks

All deploy playbooks are idempotent. Re-running them will upgrade existing Helm releases and re-apply manifests without downtime. The bootstrap playbook remembers previous answers -- press Enter to keep them.

## Roles

| Role | Used by | Purpose |
|---|---|---|
| `discover_environment` | `bootstrap.yml` | Prompt for Model A or B |
| `discover_contexts` | `bootstrap.yml` | Discover and verify kubectl contexts |
| `discover_ingress` | `bootstrap.yml` | Configure Traefik, hostnames, Pi-hole |
| `argocd_bootstrap` | (templates only) | Jinja2 templates for Argo CD manifests |
| `pihole_dns` | `deploy-dns.yml` | Register DNS records with Pi-hole v6 API |

## Configuration files

| File | Purpose |
|---|---|
| `ansible.cfg` | Ansible settings (inventory path, output format) |
| `inventory/localhost.yml` | Localhost inventory (all playbooks run locally) |
| `group_vars/all.yml` | Default variables (Argo CD version, Helm repo URLs) |

## Secrets

Pi-hole credentials are stored encrypted in `vault/secrets.yml` using Ansible Vault. The vault password is in `.vault_pass` (gitignored).

To view secrets:
```bash
ansible-vault view --vault-password-file .vault_pass vault/secrets.yml
```

To edit secrets:
```bash
ansible-vault edit --vault-password-file .vault_pass vault/secrets.yml
```

## Environment configuration

All user selections from `bootstrap.yml` are saved to `environments.yml` at the repo root. This file is loaded by all deploy playbooks and contains:
- Environment model (A or B)
- Kubectl contexts
- Git repository URL
- Ingress settings (hostnames, enabled/disabled)
- Pi-hole settings (IPs, enabled/disabled)

## Templates

Jinja2 templates in `roles/argocd_bootstrap/templates/` generate:
- Argo CD Helm values (`values.yml.j2`)
- AppProject manifests (`projects/*.j2`)
- Application manifests (`apps/{stage,prod}/*.j2`)
- Traefik IngressRoute manifests (`ingressroutes/*.j2`)
- Observability ingress values (`observability/overlays/*/ingress-values.yaml.j2`)

These are rendered by `deploy-continuousdeployment.yml` with environment-specific values and written to `argocd/` and `platform/` directories.
