# MC SpeedRun World Server Hoster — System Design

> Full design document. See README for a quick overview.

## 1. Project Overview

This platform enables users to deploy, configure, and play Minecraft speedrun worlds on-demand
using a containerized Kubernetes infrastructure hosted on a home lab cluster.

## 2. Use Case

Users visit a website, choose a speedrun world seed and settings, and get a fully containerized
Minecraft server to connect to — without any manual setup.

### User-Facing Features

- Website to browse and provision MC speedrun worlds (whitelisted seed list)
- UI to provision and manage K8s cluster resources
- Host containerized Minecraft servers on demand
- Spec fields: seed, rules/settings, game version, TTL

## 3. Infrastructure & Hardware

| Node | Role | Notes |
|------|------|-------|
| Dell PC | Control Plane + Primary Worker | Main workloads; higher CPU/RAM |
| Personal PC | Secondary Worker | Auxiliary node; monitoring stack |

> Both machines must be on the same LAN or connected via VPN.

### Networking

- Internal cluster networking: Flannel or Calico CNI
- NodePort or LoadBalancer services for MC server ports (25565+)
- Ingress controller (NGINX) for the web UI
- DDNS (DuckDNS / Cloudflare) for external access

## 4. Request Flow

1. User fills out the web form: seed, game version, rules
2. Frontend POSTs to the API backend
3. Backend creates a `MinecraftServer` CRD in K8s
4. Operator detects new CRD → deploys a Minecraft pod
5. Operator returns server IP/port → API sends to user
6. User connects their MC client to the assigned address

## 5. CRD Spec Fields

The `MinecraftServer` CRD (`mc.erikjearl.io/v1alpha1`) has been simplified to two spec fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gameVersion` | string | ✅ | Minecraft version (e.g. `"1.16.1"` or `"LATEST"`) |
| `serverProperties` | map[string]string | ❌ | Free-form map of [`itzg/minecraft-server`](https://github.com/itzg/docker-minecraft-server) env var overrides |

All server configuration (seed, game mode, difficulty, max players, whitelist, etc.) is passed through `serverProperties` as `itzg/minecraft-server` environment variable names. This avoids maintaining a fixed list of fields in the CRD schema and exposes the full configuration surface of the upstream image.

**Example:**

```yaml
spec:
  gameVersion: "1.16.1"
  serverProperties:
    GAMEMODE: survival
    DIFFICULTY: normal
    MAX_PLAYERS: "2"
    SEED: "-1234567890"
    ONLINE_MODE: "true"
    WHITE_LIST: "true"
```

**Status subresource fields:**

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | `Running` once resources are created |
| `port` | integer | Assigned NodePort |
| `address` | string | `<node-ip>:<port>` for the Minecraft client |
| `deploymentRef` | string | Name of the managed Deployment |
| `serviceRef` | string | Name of the managed Service |

`kubectl get mcs` printer columns: **Phase**, **Port**, **Version**, **Age**.

## 6. Operator (Kopf / Python)

### Code Layout

| File | Purpose |
|------|---------|
| `operator/main.py` | Kopf event handlers (`on_startup`, `on_create`, `on_update`, `on_delete`) |
| `operator/helpers.py` | Pure manifest-builder functions and utilities |

### Responsibilities

- Watch for `MinecraftServer` CRD create / update / delete events
- Reconcile desired state: create **PVC + Deployment + Service** per CRD (all owned by the CR for automatic garbage-collection on delete)
- Report status (`phase`, `port`, `address`, `deploymentRef`, `serviceRef`) back to the CRD status subresource
- Monitor pod health via Kubernetes readiness/liveness probes (no operator-level polling needed)
- _(Not yet implemented)_ Enforce TTL: delete resources after idle timeout expires

### Resource provisioning (`on_create`)

1. `build_pvc(name, namespace)` → PVC (`5Gi`, `ReadWriteOnce`, no explicit `storageClassName`)
2. `build_deployment(name, namespace, spec)` → Deployment with:
   - Image: `itzg/minecraft-server:latest`
   - Env built by `build_env(spec)`: always injects `EULA=TRUE` and `VERSION`, then merges all `spec.serverProperties` key/value pairs
   - Resource requests: `2Gi` memory / `500m` CPU; limits: `3Gi` / `2000m`
   - Recreate strategy (avoids two pods writing to the same PVC)
   - Readiness probe: `tcpSocket:25565`, initial delay 60 s, period 10 s, failure threshold 6
   - Liveness probe: `tcpSocket:25565`, initial delay 120 s, period 30 s, failure threshold 3
   - `/data` volume mount backed by the PVC
3. `build_service(name, namespace)` → NodePort Service; the assigned port is read back from the API response and written to `status.port`
4. `get_node_address(core_v1, node_port)` → resolves the first `InternalIP` of any Ready node and writes `<ip>:<port>` to `status.address`

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `WARNING`, etc.) |

Kopf's own status-posting level is clamped to `WARNING` to reduce noise from patch retries.

## 7. Web UI

### Pages

- **Home / Browse** — list available whitelisted speedrun seeds
- **Launch Server** — form: seed, version, rules, max players, whitelist
- **My Servers** — dashboard: active servers, IP/port, time remaining
- **Admin Panel** — cluster resources, node capacity, running pods

### Stack

- Frontend: Next.js + Tailwind CSS
- Backend API: FastAPI (Python) or Node.js (Express)
- Auth: invite code or GitHub OAuth

## 8. Helm Chart

Packages the full system for reproducible installs:

- Operator Deployment + RBAC
- CRD manifests
- Web UI Deployment + Service + Ingress
- API Backend Deployment + Service
- ConfigMaps for presets and whitelisted seeds
- Optional: Prometheus ServiceMonitor

## 9. Known Limitations

| Limitation | Mitigation |
|------------|------------|
| Home internet bandwidth | LAN play or Tailscale/ZeroTier VPN |
| Dynamic IP / NAT | DDNS (DuckDNS, Cloudflare) |
| 2-node capacity | Pod resource limits + priority classes |
| No HA control plane | Accepted; document recovery steps |
| Storage redundancy | local-path provisioner + manual backups |

## 10. Future Enhancements

- CRDs for Fabric, Forge, Paper, Bedrock
- Automatic world recording / replay upload
- LiveSplit / in-game timer overlay
- Discord bot (slash commands to launch servers)
- Grafana dashboard (players, uptime, resource usage)
- Horizontal pod autoscaling