# Falco (Runtime Security)

Runtime security monitoring using eBPF. Falco monitors system calls and container activity to detect suspicious behavior, policy violations, and potential threats.

## Files

| File/Directory | Purpose |
|---|---|
| `base-values.yaml` | Shared Helm values: eBPF driver, collectors, metrics, custom rules |
| `overlays/stage/values.yaml` | Stage: smaller resources, Falcosidekick with debug |
| `overlays/prod/values.yaml` | Prod: larger resources, Falcosidekick without debug |
| `rules/kustomization.yaml` | Kustomize manifest for additional resources |
| `rules/prometheusrules.yaml` | PrometheusRules for Falco health alerting |
| `rules/networkpolicy.yaml` | NetworkPolicy for Falco namespace |
| `argo-events/` | Falco -> Argo Workflows integration manifests |

## Chart

- **Chart:** `falcosecurity/falco`
- **Version:** 8.0.1
- **App Version:** 0.43.0

## Key configuration

- **Driver:** `modern_ebpf` (requires kernel 5.8+ with BTF; ClusterForge default images meet this)
- **Fallback drivers:** Change `driver.kind` to `kmod` (kernel module) or `ebpf` (legacy eBPF) for older kernels
- **Container engine:** Uses the container plugin for metadata enrichment from containerd
- **Metrics:** Enabled on port 8765, scraped by Prometheus via ServiceMonitor

## Custom rules

Custom rules are defined inline in `base-values.yaml` under the `customRules` key. They supplement (not replace) Falco's default ruleset.

### Included detections

| Rule | Priority | What it detects |
|---|---|---|
| Terminal shell in container | WARNING | Shell opened in a running container |
| Sensitive file read in container | WARNING | Reads of /etc/shadow, /etc/passwd, secrets |
| Unexpected outbound connection | NOTICE | Outbound connections on non-standard ports |
| Container privilege escalation | WARNING | sudo, su, setuid/setgid in containers |
| Crypto mining process detected | CRITICAL | Known mining processes or stratum connections |
| Unexpected K8s API access | NOTICE | Containers accessing the API server unexpectedly |

### Editing rules

Rules use Falco's YAML syntax. Key patterns:
- Use `append: false` to override an existing rule entirely
- Use `append: true` to add conditions to an existing rule
- Define macros before the rules that reference them
- All string values in conditions must be quoted (e.g., `proc.name in ("sudo", "su")`)

Platform namespaces are excluded from network rules via the `platformforge_system_namespaces` macro.

## Falcosidekick

Falcosidekick is deployed as a subchart. The Falco Helm chart automatically wires Falco to Falcosidekick when `falcosidekick.enabled: true`. It provides alert forwarding to external destinations.

To configure alert destinations, edit the Falcosidekick config in the overlay values files.

## Prometheus alerting

PrometheusRules in `rules/prometheusrules.yaml` fire alerts for:
- Falco DaemonSet pods unavailable for 5+ minutes
- No Falco events detected for 15+ minutes (possible crash)
- Critical-priority security events detected
- High event rate (>50/sec for 10+ minutes)
- Kernel event drops (needs buffer increase)

## NetworkPolicy

The NetworkPolicy in `rules/networkpolicy.yaml`:
- Default denies all traffic in the Falco namespace
- Allows Falco pods: DNS (53), K8s API (6443), HTTPS outbound (443 for falcoctl downloads), Prometheus scraping (8765)
- Allows Falcosidekick: DNS, HTTPS outbound (443 for webhooks), inbound from Falco (2801)

## Argo Workflows integration

The `argo-events/` directory contains manifests for connecting Falco alerts to Argo Workflows for automated incident response:
- `eventsource.yaml` -- Webhook endpoint receiving Falcosidekick alerts
- `sensor.yaml` -- Filters for WARNING+ events, triggers workflows
- `workflow-template.yaml` -- Customizable incident response actions

Requires Argo Events and Argo Workflows installed separately. See `argo-events/README.md` for setup instructions.
