# Traefik Ingress Controller

Traefik routes external traffic to platform services. Deployed as a LoadBalancer service via MetalLB, it provides HTTPS ingress with automatic HTTP-to-HTTPS redirect.

## Files

| File | Purpose |
|---|---|
| `base-values.yaml` | Shared Helm values: LoadBalancer, IngressClass (`traefik`), entrypoints, API access |
| `overlays/stage/values.yaml` | Stage: 1 replica, debug logging |
| `overlays/prod/values.yaml` | Prod: 2 replicas, warn logging |

## Chart

- **Chart:** `traefik/traefik`
- **Version:** 39.0.7
- **App Version:** v3.6.12

## Key configuration

- **IngressClass name:** `traefik` (fixed, not derived from Helm release name)
- **Entrypoints:** `web` (port 80, redirects to HTTPS), `websecure` (port 443, TLS)
- **Service type:** LoadBalancer (MetalLB assigns an IP)
- **API:** Enabled for internal debugging via port-forward to 8080

## IngressRoutes

PlatformForge uses Traefik IngressRoute CRDs (not standard Kubernetes Ingress) for routing. This is because Traefik v3 forces HTTPS backend connections on the `websecure` entrypoint when using standard Ingress. IngressRoutes allow explicit `scheme: http` on backend services.

IngressRoutes are created by the Ansible deploy playbooks and applied directly to each cluster. They are not managed by Argo CD since they contain environment-specific hostnames.

## Accessing the Traefik dashboard

```bash
kubectl -n traefik port-forward deploy/traefik-<env> 8080:8080
# Open http://localhost:8080/dashboard/
```
