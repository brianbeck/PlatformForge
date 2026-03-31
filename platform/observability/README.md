# Observability Stack (kube-prometheus-stack)

Full monitoring stack providing metrics collection, alerting, and dashboards. Includes Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, and the Prometheus Operator.

## Files

| File | Purpose |
|---|---|
| `base-values.yaml` | Shared values: scrape intervals, retention, Alertmanager routing, Grafana config, default alerting rules |
| `overlays/stage/values.yaml` | Stage: 7-day retention, ephemeral storage, smaller resources |
| `overlays/prod/values.yaml` | Prod: 30-day retention, 2 Prometheus replicas, 2 Alertmanager replicas |
| `overlays/stage/ingress-values.yaml` | Generated: Grafana/Prometheus ingress config for stage (if enabled) |
| `overlays/prod/ingress-values.yaml` | Generated: Grafana/Prometheus ingress config for prod (if enabled) |

## Chart

- **Chart:** `prometheus-community/kube-prometheus-stack`
- **Version:** 82.15.1
- **App Version:** v0.89.0

## Key configuration

- **ServiceMonitor discovery:** All ServiceMonitors are auto-discovered regardless of labels (`serviceMonitorSelectorNilUsesHelmValues: false`)
- **Default alerting rules:** Kubernetes API server, kubelet, etcd, node, storage rules all enabled
- **Grafana dashboards:** Sidecar auto-loads dashboards from ConfigMaps with `grafana_dashboard` label
- **Alertmanager routing:** Critical alerts routed to a separate receiver; Watchdog alerts suppressed

## Accessing services

If Traefik ingress is configured:
- **Grafana:** `https://grafana-<env>.<domain>`
- **Prometheus:** `https://prometheus-<env>.<domain>`

Via port-forward:
```bash
# Grafana
kubectl -n <monitoring-ns> port-forward svc/observability-<env>-grafana 3000:80

# Prometheus
kubectl -n <monitoring-ns> port-forward svc/prometheus-operated 9090:9090

# Alertmanager
kubectl -n <monitoring-ns> port-forward svc/alertmanager-operated 9093:9093
```

## Grafana credentials

```bash
kubectl -n <monitoring-ns> get secret observability-<env>-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d
```
Default user: `admin`

## Configuring alert destinations

Edit `overlays/prod/values.yaml` and uncomment the Alertmanager `slack_configs` section, or add PagerDuty, email, etc.

## Remote write

For long-term retention and cross-cluster visibility, uncomment `remoteWrite` in the prod overlay and point it at Thanos, Mimir, or Grafana Cloud.

## Known limitations

- Grafana persistence is disabled on prod because `local-path` StorageClass is `ReadWriteOnce` and incompatible with rolling updates. Enable when using distributed storage (Longhorn, Rook/Ceph).
