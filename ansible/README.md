# Ansible

Ansible playbooks for bootstrapping and managing PlatformForge. Ansible handles discovery, Argo CD installation, and lifecycle operations. **Argo CD owns all platform services** -- Ansible does not install Helm charts for platform services.

## Playbooks

| Playbook | Purpose | Interactive? |
|---|---|---|
| `bootstrap.yml` | Configure environment (prompts for all settings) | Yes |
| `install-argocd.yml` | Install Argo CD, apply ApplicationSets, register DNS | No |
| `deploy-dns.yml` | Re-register hostnames with Pi-hole | No |
| `healthcheck.yml` | Verify all services across all clusters | No |
| `teardown.yml` | Clean removal of all services | Yes (confirmation) |

### Typical workflow

```bash
cd ansible

# First time: configure everything
ansible-playbook playbooks/bootstrap.yml

# Install Argo CD (deploys all platform services via GitOps)
ansible-playbook playbooks/install-argocd.yml

# Commit generated ApplicationSets
cd .. && git add argocd/ && git commit -m "Generate ApplicationSets" && git push

# Check health
cd ansible && ansible-playbook playbooks/healthcheck.yml

# Tear down when needed
ansible-playbook playbooks/teardown.yml
```

## Ownership Model

| Ansible owns | Argo CD owns |
|---|---|
| Environment discovery | Traefik |
| Kubectl context validation | kube-prometheus-stack |
| Ingress/DNS configuration | Gatekeeper (controller + templates + constraints) |
| Argo CD installation | Falco |
| ApplicationSet generation | Trivy Operator |
| Pi-hole DNS registration | All platform config in `platform/` |
| Health checks | |
| Teardown | |

## Roles

| Role | Used by | Purpose |
|---|---|---|
| `discover_environment` | `bootstrap.yml` | Prompt for Model A or B |
| `discover_contexts` | `bootstrap.yml` | Discover and verify kubectl contexts |
| `discover_ingress` | `bootstrap.yml` | Configure Traefik, hostnames, Pi-hole |
| `argocd_install` | `install-argocd.yml` | Install Argo CD, template and apply ApplicationSets |
| `pihole_dns` | `install-argocd.yml`, `deploy-dns.yml` | Register DNS records with Pi-hole v6 |
