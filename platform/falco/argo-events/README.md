# Falco -> Argo Events -> Argo Workflows Integration

This directory contains manifests to connect Falco security alerts to Argo Workflows
for automated incident response.

## Architecture

```
Falco DaemonSet
    |
    v (HTTP POST)
Falcosidekick (webhook output)
    |
    v (HTTP POST)
Argo Events EventSource (webhook type, port 12000)
    |
    v (triggers)
Argo Events Sensor
    |
    v (creates)
Argo Workflow (incident response)
```

## Prerequisites

1. Argo Events installed in the cluster (namespace: `argo-events`)
2. Argo Workflows installed in the cluster (namespace: `argo`)
3. Falcosidekick webhook output configured (see Falco overlay values)

## Setup

1. Apply these manifests to your cluster:
   ```bash
   kubectl apply -f eventsource.yaml
   kubectl apply -f sensor.yaml
   kubectl apply -f workflow-template.yaml
   ```

2. Enable the Falcosidekick webhook in your Falco overlay values:
   ```yaml
   falcosidekick:
     enabled: true
     webhook:
       address: "http://falco-eventsource-svc.argo-events.svc.cluster.local:12000/falco"
   ```

3. Argo CD will sync the Falco values change, and alerts will start flowing.

## Customization

Edit `workflow-template.yaml` to define your incident response actions:
- Notify on-call (Slack, PagerDuty)
- Cordon affected nodes
- Capture forensic data
- Scale down compromised deployments
